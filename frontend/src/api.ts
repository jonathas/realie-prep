const adminHeaders = (): HeadersInit => {
  const password = sessionStorage.getItem('adminPassword')
  return password ? { 'X-Admin-Password': password } : {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Something went wrong' })) as { detail?: string | string[] }
    const detail = Array.isArray(payload.detail) ? payload.detail.join(', ') : payload.detail
    throw new Error(detail || `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  get: <T>(path: string, admin = false) => request<T>(path, { headers: admin ? adminHeaders() : {} }),
  post: <T>(path: string, body?: unknown, admin = false) => request<T>(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...(admin ? adminHeaders() : {}) }, body: body === undefined ? undefined : JSON.stringify(body),
  }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
}
