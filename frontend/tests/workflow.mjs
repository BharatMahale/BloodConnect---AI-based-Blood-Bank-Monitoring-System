import { chromium } from 'playwright-core'

const baseURL = process.env.BC_FRONTEND_URL || 'http://127.0.0.1:5173'
const executablePath = process.env.BC_BROWSER_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const credentials = {
  requester: ['requester.demo@bloodconnect.local', process.env.BC_DEMO_REQUESTER_PASSWORD],
  staff: ['staff.demo@bloodconnect.local', process.env.BC_DEMO_STAFF_PASSWORD],
  unrelated: ['unrelated.demo@bloodconnect.local', process.env.BC_DEMO_UNRELATED_PASSWORD],
}
const registrationEmail = `registration.demo.${Date.now()}@bloodconnect.local`
const registrationPassword = process.env.BC_DEMO_REGISTRATION_PASSWORD

if ([...Object.values(credentials).map(([, password]) => password), registrationPassword].some((value) => !value)) {
  throw new Error('Demo password environment variables are required.')
}

const results = []
const assert = (condition, message) => { if (!condition) throw new Error(message) }
const waitFor = async (check, message, timeout = 10000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (await check()) return
    await new Promise((resolve) => setTimeout(resolve, 150))
  }
  throw new Error(message)
}
const test = async (name, operation) => {
  try { await operation(); results.push({ name, status: 'PASS' }); process.stdout.write(`PASS ${name}\n`) }
  catch (error) { results.push({ name, status: 'FAIL', error: error.message }); process.stdout.write(`FAIL ${name}: ${error.message}\n`); throw error }
}

async function login(page, [email, password]) {
  await page.goto(`${baseURL}/login`)
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.waitForURL('**/dashboard')
  await page.getByRole('heading', { name: /Hello,/ }).waitFor()
}

async function apiCall(page, path, options = {}) {
  return page.evaluate(async ({ path, options }) => {
    const session = JSON.parse(localStorage.getItem('bloodconnect_session'))
    const response = await fetch(`/api/v1/${path.replace(/^\//, '')}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.access}`,
        ...(options.headers || {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
    let data = null
    try { data = await response.json() } catch { /* no JSON body */ }
    return { status: response.status, data }
  }, { path, options })
}

async function openActionDialog(page, title) {
  const dialog = page.getByRole('dialog', { name: title })
  await dialog.waitFor()
  assert(await dialog.getAttribute('aria-modal') === 'true', `${title} was not modal.`)
  assert(await dialog.getByRole('heading', { name: title, exact: true }).isVisible(), `${title} had no accessible heading.`)
  return dialog
}

async function submitActionDialog(page, { title, fields = [], confirm }) {
  const dialog = await openActionDialog(page, title)
  for (const field of fields) {
    const control = dialog.getByLabel(field.label)
    if (field.type === 'select') await control.selectOption(field.value)
    else await control.fill(String(field.value))
  }
  assert(await dialog.getByRole('button', { name: confirm, exact: true }).isVisible(), `${title} action button was not available.`)
  await dialog.getByRole('button', { name: confirm, exact: true }).click()
  await page.waitForTimeout(350)
}

async function createRequest(page, { bankId = '', units = 2, patient = 'BloodConnect Demo Patient' } = {}) {
  await page.goto(`${baseURL}/requests/new${bankId ? `?bank=${bankId}` : ''}`)
  await page.getByLabel('Blood group').selectOption({ label: 'O Positive' })
  await page.getByLabel('Component').selectOption({ label: 'Whole Blood' })
  await page.getByLabel('Patient name').fill(patient)
  await page.getByLabel('Units required').fill(String(units))
  await page.getByLabel('Required date').fill(new Date(Date.now() + 86400000).toISOString().slice(0, 10))
  await page.getByLabel('Hospital name').fill('BloodConnect Demo Hospital')
  await page.getByLabel('Hospital address').fill('100 BloodConnect Demo Lane, Pune')
  await page.getByLabel('Contact phone').fill('9000000002')
  await page.getByLabel('Hospital latitude').fill('18.520430')
  await page.getByLabel('Hospital longitude').fill('73.856744')
  await page.getByLabel('Additional information').fill('Isolated automated demo request; safe to remove.')
  await page.getByRole('button', { name: 'Submit blood request' }).click()
  await page.waitForURL(/\/requests\/[0-9a-f-]+$/)
  await page.getByText('Blood request submitted successfully', { exact: false }).waitFor()
  return page.url().split('/').at(-1)
}

const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-gpu'] })
const requesterContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const requester = await requesterContext.newPage()
const staffContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const staff = await staffContext.newPage()
const unrelatedContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const unrelated = await unrelatedContext.newPage()
let mainRequestId
let cancelRequestId
let bankId
let inventoryId
let stockBefore
let stockAfterFulfilment

try {
  await test('Logged-out protected route redirects to login', async () => {
    await requester.goto(`${baseURL}/dashboard`)
    await requester.waitForURL('**/login')
  })

  await test('Unsuccessful login shows an understandable error', async () => {
    await requester.getByLabel('Email address').fill(credentials.requester[0])
    await requester.getByLabel('Password').fill('invalid-local-demo-password')
    await requester.getByRole('button', { name: 'Sign in', exact: true }).click()
    await requester.getByRole('alert').waitFor()
    assert(requester.url().endsWith('/login'), 'Invalid login left the login page.')
  })

  await test('Successful login and page reload restore the session', async () => {
    await login(requester, credentials.requester)
    await requester.reload()
    await requester.getByRole('heading', { name: /Hello,/ }).waitFor()
    assert(!requester.url().endsWith('/login'), 'Reload lost the authenticated session.')
  })

  await test('Single-flight refresh works twice with rotated refresh tokens', async () => {
    let refreshRequests = 0
    const listener = (request) => { if (request.url().includes('/auth/token/refresh/')) refreshRequests += 1 }
    requester.on('request', listener)
    for (let expected = 1; expected <= 2; expected += 1) {
      await requester.evaluate(() => {
        const session = JSON.parse(localStorage.getItem('bloodconnect_session'))
        session.access = 'expired.demo.access'
        localStorage.setItem('bloodconnect_session', JSON.stringify(session))
      })
      await requester.reload()
      await requester.getByRole('heading', { name: /Hello,/ }).waitFor()
      assert(refreshRequests === expected, `Expected ${expected} refresh request(s), received ${refreshRequests}.`)
    }
    requester.off('request', listener)
  })

  await test('A network failure does not silently clear the session', async () => {
    await requester.route('**/api/v1/auth/me/', (route) => route.abort())
    await requester.reload()
    await requester.getByRole('heading', { name: /Hello,/ }).waitFor()
    assert(await requester.getByRole('button', { name: 'Log out' }).isVisible(), 'Authenticated UI disappeared after a network error.')
    await requester.unroute('**/api/v1/auth/me/')
  })

  await test('Demo bank directory and address-based nearby search render correctly', async () => {
    await requester.goto(`${baseURL}/banks`)
    await requester.getByLabel('Search').fill('BloodConnect Demo Test Bank')
    await requester.getByRole('button', { name: 'Search blood banks' }).click()
    const bankLink = requester.getByRole('link', { name: 'BloodConnect Demo Test Bank' }).first()
    await bankLink.waitFor()
    await bankLink.click()
    await requester.getByRole('heading', { name: 'BloodConnect Demo Test Bank' }).waitFor()
    await requester.locator('.inventory-list').getByText('O Positive', { exact: true }).waitFor()
    await requester.locator('.inventory-list').getByText('Whole Blood', { exact: true }).waitFor()
    const bankResponse = await apiCall(requester, 'blood-banks/?search=BloodConnect%20Demo%20Test%20Bank')
    assert(bankResponse.status === 200 && bankResponse.data.results.length === 1, 'Demo bank API search was not unique.')
    bankId = bankResponse.data.results[0].id
    await requester.goto(`${baseURL}/banks`)
    await requester.getByRole('button', { name: 'Nearby search' }).click()
    assert(await requester.getByLabel('Address').isVisible(), 'Address input is missing.')
    assert(await requester.getByLabel('Latitude', { exact: true }).count() === 0, 'Latitude input is visible.')
    assert(await requester.getByLabel('Longitude', { exact: true }).count() === 0, 'Longitude input is visible.')
    assert(await requester.getByRole('combobox', { name: 'Radius' }).isVisible(), 'Radius selector is missing.')
    let forwardCalls = 0; let nearbyCalls = 0
    await requester.route('**/api/v1/locations/geocode/', (route) => {
      forwardCalls += 1
      const address = route.request().postDataJSON().address
      if (address === 'Unknown location') return route.fulfill({ status: 404, json: { detail: 'No result' } })
      if (address === 'Service down') return route.fulfill({ status: 503, json: { detail: 'Location lookup is temporarily unavailable. Please try again.' } })
      return route.fulfill({ json: { address: 'Pune, Maharashtra, India', latitude: 18.52043, longitude: 73.856744 } })
    })
    requester.on('request', (request) => { if (request.url().includes('/blood-banks/nearby/')) nearbyCalls += 1 })
    await requester.getByLabel('Address').fill('Pune, Maharashtra')
    await requester.getByRole('button', { name: 'Search blood banks' }).click()
    await requester.getByRole('link', { name: 'BloodConnect Demo Test Bank' }).waitFor()
    assert(await requester.getByLabel('Address').inputValue() === 'Pune, Maharashtra, India', 'Canonical address was not shown.')
    await requester.getByRole('combobox', { name: 'Radius' }).selectOption('10')
    await requester.getByRole('button', { name: 'Search blood banks' }).click()
    await waitFor(() => nearbyCalls === 2, 'Radius change did not repeat nearby search.')
    assert(forwardCalls === 1, 'Radius change repeated forward geocoding.')
    await requester.getByLabel('Address').fill('Unknown location')
    await requester.getByRole('button', { name: 'Search blood banks' }).click()
    await requester.getByRole('alert').waitFor()
    assert(nearbyCalls === 2, 'Unresolved address called nearby search with stale coordinates.')
    await requesterContext.grantPermissions(['geolocation'])
    await requesterContext.setGeolocation({ latitude: 18.52043, longitude: 73.856744 })
    await requester.route('**/api/v1/locations/reverse-geocode/', (route) => route.fulfill({ json: { address: 'Pune, Maharashtra, India', latitude: 18.52043, longitude: 73.856744 } }))
    await requester.getByRole('button', { name: 'Use my current location' }).click()
    await waitFor(async () => (await requester.getByLabel('Address').inputValue()) === 'Pune, Maharashtra, India', 'Current location did not become a readable address.')
    assert(!(await requester.getByRole('region', { name: 'Location' }).innerText()).includes('18.52043'), 'Raw coordinates are visible.')
    await requester.getByRole('button', { name: 'Search blood banks' }).click()
    await requester.getByRole('link', { name: 'BloodConnect Demo Test Bank' }).waitFor()
    await requester.evaluate(() => Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined }))
    await requester.getByRole('button', { name: 'Use my current location' }).click()
    await requester.getByRole('alert').getByText('Geolocation is unavailable. Enter an address manually.').waitFor()
    await requester.evaluate(() => Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (_success, failure) => failure({ code: 1 }) } }))
    await requester.getByRole('button', { name: 'Use my current location' }).click()
    await requester.getByRole('alert').getByText('Location access was denied. Enter an address manually.').waitFor()
    await requester.getByLabel('Address').fill('Service down')
    const callsBeforeFailure = nearbyCalls
    await requester.getByRole('button', { name: 'Search blood banks' }).click()
    await requester.getByRole('alert').getByText('Location lookup is temporarily unavailable. Please try again.').waitFor()
    assert(nearbyCalls === callsBeforeFailure, 'Provider failure called nearby search.')
    await requester.unroute('**/api/v1/locations/geocode/')
    await requester.unroute('**/api/v1/locations/reverse-geocode/')
  })

  await test('Request validation, creation, history, suggestions and assignment work in the UI', async () => {
    await requester.goto(`${baseURL}/requests/new`)
    await requester.getByLabel('Blood group').selectOption({ label: 'O Positive' })
    await requester.getByLabel('Component').selectOption({ label: 'Whole Blood' })
    await requester.getByLabel('Patient name').fill('BloodConnect Demo Main Patient')
    await requester.getByLabel('Units required').fill('2')
    await requester.getByLabel('Required date').fill(new Date(Date.now() + 86400000).toISOString().slice(0, 10))
    await requester.getByLabel('Hospital name').fill('BloodConnect Demo Hospital')
    await requester.getByLabel('Hospital address').fill('100 BloodConnect Demo Lane, Pune')
    await requester.getByLabel('Contact phone').fill('9000000002')
    await requester.getByLabel('Hospital latitude').fill('18.520430')
    await requester.getByRole('button', { name: 'Submit blood request' }).click()
    await requester.locator('.field-error').getByText('must be provided together', { exact: false }).waitFor()
    await requester.getByLabel('Hospital longitude').fill('73.856744')
    await requester.getByRole('button', { name: 'Submit blood request' }).click()
    await requester.waitForURL(/\/requests\/[0-9a-f-]+$/)
    mainRequestId = requester.url().split('/').at(-1)
    await requester.getByText('Pending', { exact: true }).first().waitFor()
    await requester.getByText('Blood request submitted.', { exact: true }).waitFor()
    await requester.getByRole('button', { name: 'Find matching banks' }).click()
    await requester.getByText('BloodConnect Demo Test Bank', { exact: true }).waitFor()
    const demoSuggestion = requester.locator('.suggestion-row').filter({ hasText: 'BloodConnect Demo Test Bank' })
    await demoSuggestion.getByRole('button', { name: 'Assign bank' }).click()
    await requester.waitForTimeout(350)
    await waitFor(async () => (await requester.locator('body').innerText()).includes('BloodConnect Demo Test Bank'), 'Assigned bank did not appear without reload.')
  })

  await login(staff, credentials.staff)
  await test('Owner workspace is scoped to owned inventory and assigned requests', async () => {
    await staff.goto(`${baseURL}/workspace`)
    await staff.getByRole('heading', { name: 'Blood-bank operations' }).waitFor()
    const pageText = await staff.locator('body').innerText()
    assert(pageText.includes('BloodConnect Demo Test Bank'), 'Owned demo inventory was missing.')
    const inventoryResponse = await apiCall(staff, 'inventory/?owned=true')
    assert(inventoryResponse.status === 200 && inventoryResponse.data.results.every((row) => row.blood_bank_name === 'BloodConnect Demo Test Bank'), 'Owned inventory API leaked another bank.')
    const requestResponse = await apiCall(staff, 'blood-requests/?assigned_to_my_bank=true')
    assert(requestResponse.status === 200 && requestResponse.data.results.some((row) => row.id === mainRequestId), 'Assigned request was missing from staff scope.')
    inventoryId = inventoryResponse.data.results.find((row) => row.blood_group_name === 'O Positive' && row.component_name === 'Whole Blood').id
    stockBefore = inventoryResponse.data.results.find((row) => row.id === inventoryId)
  })

  await test('Owner reviews, accepts, reserves and fulfils without stale UI or duplicate movement', async () => {
    await staff.goto(`${baseURL}/requests/${mainRequestId}`)
    await staff.getByRole('button', { name: 'Update status' }).click()
    await submitActionDialog(staff, { title: 'Update request status', fields: [{ label: 'New status', type: 'select', value: 'UNDER_REVIEW' }, { label: 'Status note', value: 'Demo review started' }], confirm: 'Update status' })
    await staff.getByText('Under Review', { exact: true }).first().waitFor()
    await staff.getByRole('button', { name: 'Update status' }).click()
    await submitActionDialog(staff, { title: 'Update request status', fields: [{ label: 'New status', type: 'select', value: 'ACCEPTED' }, { label: 'Status note', value: 'Demo request accepted' }], confirm: 'Update status' })
    await staff.getByText('Accepted', { exact: true }).first().waitFor()
    const reserve = staff.getByRole('button', { name: 'Reserve stock' })
    await reserve.click()
    await submitActionDialog(staff, { title: 'Reserve inventory', fields: [{ label: 'Units to reserve', value: 2 }], confirm: 'Reserve stock' })
    await waitFor(async () => (await staff.locator('body').innerText()).includes('2 reserved'), 'Reservation did not update in place.')
    let inventory = await apiCall(staff, `inventory/${inventoryId}/`)
    assert(inventory.data.reserved_units === stockBefore.reserved_units + 2, 'Duplicate click created an incorrect reservation quantity.')
    await staff.getByRole('button', { name: 'Fulfil' }).click()
    await submitActionDialog(staff, { title: 'Fulfil reserved inventory', fields: [{ label: 'Units to fulfil', value: 2 }, { label: 'Fulfilment note', value: 'BloodConnect demo fulfilment' }], confirm: 'Record fulfilment' })
    await staff.getByText('Completed', { exact: true }).first().waitFor()
    inventory = await apiCall(staff, `inventory/${inventoryId}/`)
    stockAfterFulfilment = inventory.data
    assert(inventory.data.total_units === stockBefore.total_units - 2, 'Fulfilment did not reduce total stock by two.')
    assert(inventory.data.reserved_units === stockBefore.reserved_units, 'Fulfilment did not release the reservation.')
    const detail = await apiCall(staff, `blood-requests/${mainRequestId}/`)
    assert(detail.data.status === 'COMPLETED' && detail.data.status_history.length >= 4, 'Completed request history was incomplete.')
    await staff.goto(`${baseURL}/workspace`)
    const inventoryRow = staff.getByRole('row').filter({ hasText: 'O Positive' }).filter({ hasText: 'Whole Blood' }).first()
    await inventoryRow.getByRole('button', { name: 'Update stock' }).click()
    await submitActionDialog(staff, { title: 'Update inventory', fields: [{ label: 'Transaction type', type: 'select', value: 'RECEIVED' }, { label: 'Quantity', value: 1 }, { label: 'Reason', value: 'Accessibility harness stock check' }, { label: 'Reference number', value: 'BC-STEP13-RECEIVE' }], confirm: 'Save stock update' })
    await inventoryRow.getByRole('button', { name: 'Update stock' }).click()
    await submitActionDialog(staff, { title: 'Update inventory', fields: [{ label: 'Transaction type', type: 'select', value: 'EXPIRED' }, { label: 'Quantity', value: 1 }, { label: 'Reason', value: 'Accessibility harness stock reversal' }, { label: 'Reference number', value: 'BC-STEP13-EXPIRE' }], confirm: 'Save stock update' })
    await inventoryRow.getByRole('button', { name: 'History' }).click()
    const historyDialog = await openActionDialog(staff, 'Transaction history')
    assert(await historyDialog.getByText('Accessibility harness stock reversal', { exact: true }).isVisible(), 'Transaction history did not show the stock check.')
    await historyDialog.getByRole('button', { name: 'Close dialog' }).click()
  })

  await test('Cancellation releases a separate reservation without changing total stock', async () => {
    const releaseRequestId = await createRequest(requester, { bankId, units: 1, patient: 'BloodConnect Demo Release Patient' })
    await staff.goto(`${baseURL}/requests/${releaseRequestId}`)
    await staff.getByRole('button', { name: 'Update status' }).click()
    await submitActionDialog(staff, { title: 'Update request status', fields: [{ label: 'New status', type: 'select', value: 'UNDER_REVIEW' }, { label: 'Status note', value: 'Release-path review' }], confirm: 'Update status' })
    await staff.getByRole('button', { name: 'Update status' }).click()
    await submitActionDialog(staff, { title: 'Update request status', fields: [{ label: 'New status', type: 'select', value: 'ACCEPTED' }, { label: 'Status note', value: 'Release-path accepted' }], confirm: 'Update status' })
    await staff.getByRole('button', { name: 'Reserve stock' }).click()
    await submitActionDialog(staff, { title: 'Reserve inventory', fields: [{ label: 'Units to reserve', value: 1 }], confirm: 'Reserve stock' })
    await staff.getByRole('button', { name: 'Release' }).click()
    await submitActionDialog(staff, { title: 'Release reservation', fields: [{ label: 'Release reason', value: 'Accessibility harness release check' }], confirm: 'Release reservation' })

    cancelRequestId = await createRequest(requester, { bankId, units: 1, patient: 'BloodConnect Demo Cancellation Patient' })
    await staff.goto(`${baseURL}/requests/${cancelRequestId}`)
    await staff.getByRole('button', { name: 'Update status' }).click()
    await submitActionDialog(staff, { title: 'Update request status', fields: [{ label: 'New status', type: 'select', value: 'UNDER_REVIEW' }, { label: 'Status note', value: 'Cancellation-path review' }], confirm: 'Update status' })
    await staff.getByRole('button', { name: 'Update status' }).click()
    await submitActionDialog(staff, { title: 'Update request status', fields: [{ label: 'New status', type: 'select', value: 'ACCEPTED' }, { label: 'Status note', value: 'Cancellation-path accepted' }], confirm: 'Update status' })
    await staff.getByRole('button', { name: 'Reserve stock' }).click()
    await submitActionDialog(staff, { title: 'Reserve inventory', fields: [{ label: 'Units to reserve', value: 1 }], confirm: 'Reserve stock' })
    let inventory = await apiCall(staff, `inventory/${inventoryId}/`)
    assert(inventory.data.reserved_units === stockAfterFulfilment.reserved_units + 1, 'Cancellation test reservation was not created.')
    await requester.goto(`${baseURL}/requests/${cancelRequestId}`)
    await requester.getByRole('button', { name: 'Cancel request' }).click()
    await submitActionDialog(requester, { title: 'Cancel blood request', fields: [{ label: 'Cancellation reason', value: 'BloodConnect demo cancellation' }], confirm: 'Cancel request' })
    await requester.getByText('Cancelled', { exact: true }).first().waitFor()
    inventory = await apiCall(staff, `inventory/${inventoryId}/`)
    assert(inventory.data.total_units === stockAfterFulfilment.total_units, 'Cancellation changed physical stock.')
    assert(inventory.data.reserved_units === stockAfterFulfilment.reserved_units, 'Cancellation did not release reserved stock.')
  })

  await test('Donor edit, availability change, screening and history screen work', async () => {
    await requester.goto(`${baseURL}/donor`)
    await requester.getByLabel('City').fill('Pune Demo Updated')
    const availability = requester.getByLabel(/currently available/)
    if (await availability.isChecked()) await availability.uncheck()
    const saveResponse = requester.waitForResponse((response) => response.url().endsWith('/api/v1/donors/me/') && response.request().method() === 'PATCH')
    await requester.getByRole('button', { name: 'Save changes' }).click()
    assert((await saveResponse).status() === 200, 'Donor profile update API did not succeed.')
    await waitFor(async () => (await apiCall(requester, 'donors/me/')).data.city === 'Pune Demo Updated', 'Donor edit did not persist.')
    await requester.getByRole('button', { name: 'Start questionnaire' }).click()
    const screeningDialog = await openActionDialog(requester, 'Preliminary donor screening')
    await screeningDialog.getByLabel('Are you feeling well today?').selectOption('yes')
    assert(await screeningDialog.getByRole('button', { name: 'Submit assessment', exact: true }).isVisible(), 'Screening dialog action button was not available.')
    await screeningDialog.getByRole('button', { name: 'Submit assessment', exact: true }).click()
    await requester.getByText('This is not clinical approval.', { exact: false }).waitFor()
    assert((await requester.locator('body').innerText()).includes('Donation history'), 'Donation history screen was not rendered.')
  })

  await test('One notification and then all notifications can be marked read', async () => {
    await requester.goto(`${baseURL}/notifications`)
    await requester.getByRole('heading', { name: 'Notifications' }).waitFor()
    const one = requester.getByRole('button', { name: 'Mark read' }).first()
    if (await one.count()) {
      const responsePromise = requester.waitForResponse((response) => response.url().includes('/mark-read/'))
      await one.click()
      assert((await responsePromise).status() === 200, 'Mark-one API did not succeed.')
    }
    const all = requester.getByRole('button', { name: 'Mark all as read' })
    const unreadBeforeAll = await apiCall(requester, 'notifications/unread-count/')
    if (unreadBeforeAll.data.unread_count > 0) {
      assert(await all.count() === 1, `Mark-all control was missing on ${requester.url()}.`)
      const responsePromise = requester.waitForResponse((response) => response.url().includes('/mark-all-read/'))
      await all.click()
      assert((await responsePromise).status() === 200, 'Mark-all API did not succeed.')
    }
    await waitFor(async () => {
      const count = await apiCall(requester, 'notifications/unread-count/')
      return count.status === 200 && count.data.unread_count === 0
    }, 'Unread notification count did not reach zero.')
    await requester.goto(`${baseURL}/dashboard`)
    await waitFor(async () => (await requester.locator('body').innerText()).includes('Unread notifications'), 'Dashboard notification counter was missing.')
  })

  await login(unrelated, credentials.unrelated)
  await test('Unrelated user is denied request, stock and staff operations by the server', async () => {
    const requestRead = await apiCall(unrelated, `blood-requests/${mainRequestId}/`)
    const stockWrite = await apiCall(unrelated, `inventory/${inventoryId}/update-stock/`, { method: 'POST', body: { transaction_type: 'RECEIVED', quantity: 1, reason: 'Unauthorized demo attempt' } })
    const staffWrite = await apiCall(unrelated, `blood-requests/${cancelRequestId}/update-status/`, { method: 'POST', body: { new_status: 'UNDER_REVIEW', note: '' } })
    assert([403, 404].includes(requestRead.status), `Request detail returned ${requestRead.status}.`)
    assert([403, 404].includes(stockWrite.status), `Stock update returned ${stockWrite.status}.`)
    assert([403, 404].includes(staffWrite.status), `Staff action returned ${staffWrite.status}.`)
  })

  await test('Empty and backend-offline states render without clearing authentication', async () => {
    await unrelated.goto(`${baseURL}/requests`)
    await unrelated.getByText('No requests found', { exact: true }).waitFor()
    await unrelated.route('**/api/v1/dashboard/me/', (route) => route.abort())
    await unrelated.goto(`${baseURL}/`)
    await unrelated.goto(`${baseURL}/dashboard`)
    await unrelated.getByText('The server could not be reached', { exact: false }).waitFor()
    assert(await unrelated.getByRole('button', { name: 'Log out' }).isVisible(), 'Offline state cleared the UI session.')
    await unrelated.unroute('**/api/v1/dashboard/me/')
  })

  await test('Registration succeeds with a unique local demo account', async () => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    await page.goto(`${baseURL}/register`)
    await page.getByLabel('First name').fill('Browser')
    await page.getByLabel('Last name').fill('Registration Demo')
    await page.getByLabel('Email address').fill(registrationEmail)
    await page.getByLabel('Phone number').fill('9000000003')
    await page.getByLabel('I’m joining as').selectOption('SEEKER')
    await page.getByLabel('Password', { exact: true }).fill(registrationPassword)
    await page.getByLabel('Confirm password').fill(registrationPassword)
    await page.getByRole('button', { name: 'Create my account' }).click()
    await page.waitForURL('**/dashboard')
    await page.getByRole('heading', { name: /Hello,/ }).waitFor()
    await context.close()
  })

  await test('Logout calls the backend and clears the frontend session', async () => {
    const responsePromise = requester.waitForResponse((response) => response.url().includes('/auth/logout/'))
    await requester.getByRole('button', { name: 'Log out' }).click()
    const response = await responsePromise
    assert(response.status() === 200, `Backend logout returned ${response.status()}.`)
    await requester.goto(`${baseURL}/dashboard`)
    await requester.waitForURL('**/login')
    assert(await requester.evaluate(() => localStorage.getItem('bloodconnect_session')) === null, 'Session storage was not cleared.')
  })

  await test('Mobile and desktop layouts have no horizontal overflow or clipped key actions', async () => {
    for (const viewport of [{ width: 375, height: 812 }, { width: 1440, height: 900 }]) {
      const context = await browser.newContext({ viewport })
      const page = await context.newPage()
      await page.goto(`${baseURL}/`)
      const metrics = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }))
      assert(metrics.scrollWidth <= metrics.width, `${viewport.width}px homepage overflowed horizontally.`)
      const primaryAction = page.getByRole('link', { name: /Find blood banks/ }).first()
      await primaryAction.waitFor()
      assert(await primaryAction.isVisible(), `${viewport.width}px primary action was hidden.`)
      await page.goto(`${baseURL}/login`)
      const submit = await page.getByRole('button', { name: 'Sign in', exact: true }).boundingBox()
      assert(submit && submit.x >= 0 && submit.x + submit.width <= viewport.width, `${viewport.width}px login submit was clipped.`)
      await context.close()
    }
  })
} finally {
  await requesterContext.close()
  await staffContext.close()
  await unrelatedContext.close()
  await browser.close()
}

process.stdout.write(`REGISTRATION_DEMO_EMAIL ${registrationEmail}\n`)
process.stdout.write(`SUMMARY ${results.filter((result) => result.status === 'PASS').length}/${results.length} passed\n`)
