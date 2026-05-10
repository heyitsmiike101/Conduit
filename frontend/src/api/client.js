/**
 * Base HTTP client for the Conduit API.
 *
 * All resource-specific files import `api` from here and call
 * api.get / api.post / api.patch / api.delete.
 */

const BASE = '/api/v1'

async function request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) {
    opts.body = JSON.stringify(body)
  }

  const res = await fetch(`${BASE}${path}`, opts)

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const json = await res.json()
      detail = json.detail || detail
    } catch {
      // response body isn't JSON — use status string
    }
    throw new Error(detail)
  }

  // 204 No Content
  if (res.status === 204) return null

  return res.json()
}

/** Multipart/form-data upload — browser sets Content-Type + boundary automatically. */
async function requestForm(method, path, formData) {
  const res = await fetch(`${BASE}${path}`, { method, body: formData })

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const json = await res.json()
      detail = json.detail || detail
    } catch {}
    throw new Error(detail)
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get:      (path)           => request('GET',    path),
  post:     (path, body)     => request('POST',   path, body),
  put:      (path, body)     => request('PUT',    path, body),
  patch:    (path, body)     => request('PATCH',  path, body),
  delete:   (path)           => request('DELETE', path),
  postForm: (path, formData) => requestForm('POST', path, formData),
}
