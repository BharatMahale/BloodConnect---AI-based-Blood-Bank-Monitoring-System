import { chromium } from 'playwright-core'

const baseURL = process.env.BC_FRONTEND_URL || 'http://127.0.0.1:5173'
const executablePath = process.env.BC_BROWSER_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const requesterCredentials = ['requester.demo@bloodconnect.local', process.env.BC_DEMO_REQUESTER_PASSWORD]
const staffCredentials = ['staff.demo@bloodconnect.local', process.env.BC_DEMO_STAFF_PASSWORD]
if (!requesterCredentials[1] || !staffCredentials[1]) throw new Error('BC_DEMO_REQUESTER_PASSWORD and BC_DEMO_STAFF_PASSWORD are required.')

const assert = (condition, message) => { if (!condition) throw new Error(message) }
const results = []
const test = async (name, fn) => { try { await fn(); results.push(`PASS ${name}`); console.log(`PASS ${name}`) } catch (error) { console.error(`FAIL ${name}: ${error.message}`); throw error } }

async function login(page, [email, password]) {
  await page.goto(`${baseURL}/login`)
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.waitForURL('**/dashboard')
}

async function api(page, path, options = {}) {
  return page.evaluate(async ({ path, options }) => {
    const session = JSON.parse(localStorage.getItem('bloodconnect_session'))
    const response = await fetch(`/api/v1/${path}`, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.access}` }, body: options.body ? JSON.stringify(options.body) : undefined })
    return { status: response.status, data: await response.json() }
  }, { path, options })
}

async function assertOpenFocus(page, dialog) {
  await dialog.waitFor()
  assert(await dialog.evaluate((node) => node.contains(document.activeElement)), 'Focus did not move into the dialog.')
}

async function assertTrap(page, dialog) {
  const controls = dialog.locator('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')
  const count = await controls.count()
  assert(count >= 1, 'Dialog did not contain a keyboard control.')
  for (let index = 0; index < count + 1; index += 1) {
    await page.keyboard.press('Tab')
    assert(await dialog.evaluate((node) => node.contains(document.activeElement)), 'Tab escaped the dialog.')
  }
  await page.keyboard.press('Shift+Tab')
  assert(await dialog.evaluate((node) => node.contains(document.activeElement)), 'Shift+Tab escaped the dialog.')
}

async function assertEscapeRestores(page, trigger, title) {
  await trigger.focus()
  await trigger.press('Enter')
  const dialog = page.getByRole('dialog', { name: title })
  await assertOpenFocus(page, dialog)
  await assertTrap(page, dialog)
  await page.keyboard.press('Escape')
  await assert(await dialog.count() === 0, `${title} remained open after Escape.`)
  assert(await trigger.evaluate((node) => document.activeElement === node), `${title} did not restore focus to its trigger.`)
}

async function assertButtonRestores(page, trigger, title, buttonName) {
  await trigger.focus()
  await trigger.press('Enter')
  const dialog = page.getByRole('dialog', { name: title })
  await assertOpenFocus(page, dialog)
  await dialog.getByRole('button', { name: buttonName, exact: true }).click()
  await assert(await dialog.count() === 0, `${title} remained open after ${buttonName}.`)
  assert(await trigger.evaluate((node) => document.activeElement === node), `${title} did not restore focus after ${buttonName}.`)
}

const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-gpu'] })
const requesterContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const staffContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const requester = await requesterContext.newPage()
const staff = await staffContext.newPage()

try {
  await login(requester, requesterCredentials)
  await login(staff, staffCredentials)
  const bank = (await api(staff, 'blood-banks/?search=BloodConnect%20Demo%20Test%20Bank')).data.results[0]
  const groups = (await api(requester, 'blood-groups/')).data
  const components = (await api(requester, 'blood-components/')).data
  const create = await api(requester, 'blood-requests/', { method: 'POST', body: { blood_bank: bank.id, blood_group: groups.find((row) => row.name === 'O Positive').id, component: components.find((row) => row.name === 'Whole Blood').id, patient_name: `Accessibility ${Date.now()}`, units_required: 1, required_date: new Date(Date.now() + 86400000).toISOString().slice(0, 10), hospital_name: 'Accessibility Test Hospital', hospital_address: 'Test address', contact_phone: '9000000000', urgency: 'URGENT' } })
  assert(create.status === 201, 'Could not create the isolated accessibility request.')
  const requestId = create.data.blood_request.id

  await test('Skip link and icon/menu controls are keyboard accessible', async () => {
    await requester.goto(`${baseURL}/`)
    const skip = requester.getByRole('link', { name: 'Skip to content' })
    await skip.waitFor()
    await requester.keyboard.press('Tab')
    assert(await skip.evaluate((node) => document.activeElement === node), 'Skip link was not first in the keyboard order.')
    await requester.keyboard.press('Enter')
    assert(await requester.locator('#main').evaluate((node) => document.activeElement === node), 'Skip link did not move focus to main content.')
    await requester.setViewportSize({ width: 375, height: 812 })
    const menu = requester.getByRole('button', { name: 'Toggle menu' })
    await menu.focus(); await menu.press('Space')
    assert(await menu.getAttribute('aria-expanded') === 'true', 'Mobile menu did not activate from the keyboard.')
    await requester.setViewportSize({ width: 1440, height: 900 })
    const notifications = requester.getByRole('link', { name: 'Notifications' })
    await notifications.focus(); await notifications.press('Enter')
    await requester.getByRole('heading', { name: 'Notifications' }).waitFor()
  })

  await test('Nearby search labels and location action work from the keyboard', async () => {
    await requester.goto(`${baseURL}/banks`)
    const tab = requester.getByRole('button', { name: 'Nearby search' })
    await tab.focus(); await tab.press('Enter')
    assert(await requester.getByLabel('Address').isVisible(), 'Address input has no label.')
    assert(await requester.getByRole('combobox', { name: 'Radius' }).isVisible(), 'Radius control has no label.')
    const location = requester.getByRole('button', { name: 'Use my current location' })
    assert(await location.isVisible(), 'Current-location button has no accessible name.')
    await requester.getByLabel('Address').focus()
    await requester.keyboard.press('Tab')
    assert(await location.evaluate((node) => document.activeElement === node), 'Current-location action is missing from keyboard order.')
    await requester.keyboard.press('Tab')
    assert(await requester.getByRole('combobox', { name: 'Radius' }).evaluate((node) => document.activeElement === node), 'Radius is missing from keyboard order.')
    assert(await requester.getByLabel('Latitude', { exact: true }).count() === 0, 'Coordinate input appeared in Nearby Search.')
  })

  await test('Request status, reservation and cancellation dialogs trap and restore focus', async () => {
    await staff.goto(`${baseURL}/requests/${requestId}`)
    await assertEscapeRestores(staff, staff.getByRole('button', { name: 'Update status' }), 'Update request status')
    const underReview = await api(staff, `blood-requests/${requestId}/update-status/`, { method: 'POST', body: { new_status: 'UNDER_REVIEW', note: 'Accessibility fixture setup' } })
    assert(underReview.status === 200, 'Could not prepare the accessibility request for acceptance.')
    const accepted = await api(staff, `blood-requests/${requestId}/update-status/`, { method: 'POST', body: { new_status: 'ACCEPTED', note: 'Accessibility fixture setup' } })
    assert(accepted.status === 200, 'Could not prepare the accessibility request for reservation.')
    await staff.reload()
    const reserve = staff.getByRole('button', { name: 'Reserve stock' })
    await reserve.click()
    const reserveDialog = staff.getByRole('dialog', { name: 'Reserve inventory' })
    await assertOpenFocus(staff, reserveDialog); await assertTrap(staff, reserveDialog)
    await reserveDialog.getByRole('button', { name: 'Reserve stock' }).click()
    assert(await reserveDialog.getByLabel('Units to reserve').getAttribute('aria-invalid') === 'true', 'Invalid reservation quantity was not marked invalid.')
    await reserveDialog.getByLabel('Units to reserve').fill('1')
    await reserveDialog.getByRole('button', { name: 'Reserve stock' }).click()
    await reserveDialog.waitFor({ state: 'detached' })
    await staff.getByRole('button', { name: 'Fulfil' }).waitFor()
    await requester.goto(`${baseURL}/requests/${requestId}`)
    await assertEscapeRestores(requester, requester.getByRole('button', { name: 'Cancel request' }), 'Cancel blood request')
    await assertButtonRestores(requester, requester.getByRole('button', { name: 'Cancel request' }), 'Cancel blood request', 'Cancel')
  })

  await test('Fulfilment, release, inventory, history, and donor screening dialogs keep focus isolated', async () => {
    await staff.goto(`${baseURL}/requests/${requestId}`)
    await assertEscapeRestores(staff, staff.getByRole('button', { name: 'Fulfil' }), 'Fulfil reserved inventory')
    await assertEscapeRestores(staff, staff.getByRole('button', { name: 'Release' }), 'Release reservation')
    await staff.goto(`${baseURL}/workspace`)
    const row = staff.getByRole('row').filter({ hasText: 'O Positive' }).filter({ hasText: 'Whole Blood' }).first()
    await assertEscapeRestores(staff, row.getByRole('button', { name: 'Update stock' }), 'Update inventory')
    await assertEscapeRestores(staff, row.getByRole('button', { name: 'History' }), 'Transaction history')
    await assertButtonRestores(staff, row.getByRole('button', { name: 'History' }), 'Transaction history', 'Close dialog')
    await requester.goto(`${baseURL}/donor`)
    await assertEscapeRestores(requester, requester.getByRole('button', { name: 'Start questionnaire' }), 'Preliminary donor screening')
    await assertButtonRestores(requester, requester.getByRole('button', { name: 'Start questionnaire' }), 'Preliminary donor screening', 'Cancel')
  })
} finally {
  await requesterContext.close(); await staffContext.close(); await browser.close()
}

console.log(`SUMMARY ${results.length}/${results.length} passed`)
