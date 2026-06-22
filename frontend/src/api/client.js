const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export async function apiFetch(path, options = {}) {
  const url = `${BASE_URL}${path}`
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!resp.ok) {
    let message = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      message = body?.detail?.message || body?.detail || message
    } catch {}
    throw { status: resp.status, message }
  }
  return resp.json()
}
