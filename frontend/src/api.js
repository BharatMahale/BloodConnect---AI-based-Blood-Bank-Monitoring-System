const API_ROOT = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
const STORAGE_KEY = 'bloodconnect_session'
let refreshPromise = null

export const sessionStore = {
  get() { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) } catch { return null } },
  set(value) { value ? localStorage.setItem(STORAGE_KEY, JSON.stringify(value)) : localStorage.removeItem(STORAGE_KEY) },
}

function endpoint(path) {
  if (/^https?:\/\//i.test(path)) throw new Error('External API URLs are not allowed.')
  return `${API_ROOT}/${String(path).replace(/^\/+/, '')}`
}

async function parseResponse(response) {
  if (response.status === 204) return null
  const type = response.headers.get('content-type') || ''
  return type.includes('json') ? response.json() : { detail: await response.text() }
}

export function errorMessage(error) {
  const data = error?.data
  if (!data) return error?.message === 'Failed to fetch' ? 'The server could not be reached. Check your connection and try again.' : (error?.message || 'Something went wrong.')
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const first = Object.values(data)[0]
  return Array.isArray(first) ? first[0] : (typeof first === 'string' ? first : 'Please review the highlighted information.')
}

export function fieldErrors(error) {
  const data = error?.data
  if (!data || typeof data !== 'object' || data.detail) return {}
  return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, Array.isArray(value) ? value.join(' ') : String(value)]))
}

async function refreshSession() {
  if (refreshPromise) return refreshPromise
  const current = sessionStore.get()
  if (!current?.refresh) return null
  refreshPromise = fetch(endpoint('auth/token/refresh/'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh: current.refresh }),
  }).then(async (response) => {
    const data = await parseResponse(response)
    if (!response.ok) { sessionStore.set(null); window.dispatchEvent(new Event('bloodconnect:session')); return null }
    const next = { ...current, access: data.access, refresh: data.refresh || current.refresh }
    sessionStore.set(next)
    return next
  }).catch(() => null).finally(() => { refreshPromise = null })
  return refreshPromise
}

export async function api(path, options = {}, retry = true) {
  const session = sessionStore.get()
  const headers = { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers }
  if (session?.access) headers.Authorization = `Bearer ${session.access}`
  let response
  try { response = await fetch(endpoint(path), { ...options, headers }) }
  catch (error) { error.isNetworkError = true; throw error }
  if (response.status === 401 && retry && session?.refresh) {
    const renewed = await refreshSession()
    if (renewed) return api(path, options, false)
  }
  const data = await parseResponse(response)
  if (!response.ok) { const error = new Error('API request failed'); error.status = response.status; error.data = data; throw error }
  return data
}

export const query = (path, params = {}) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => { if (value !== '' && value !== undefined && value !== null) search.set(key, value) })
  return api(`${path}${search.size ? `?${search}` : ''}`)
}

export const asList = (data) => Array.isArray(data) ? data : (data?.results || [])
