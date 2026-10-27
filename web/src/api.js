// Appels à l'API FastAPI, servie sous /api (proxy Vite en dev, nginx en prod).
async function request(method, path, body) {
  const opts = { method, headers: {} }
  if (body instanceof FormData) opts.body = body
  else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const resp = await fetch(`/api${path}`, opts)
  const data = resp.headers.get('content-type')?.includes('json') ? await resp.json() : null
  if (!resp.ok) {
    const detail = data?.detail
    const error = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail ?? resp.statusText))
    error.status = resp.status
    error.detail = detail  // ex. contrôles refusés au dépôt : { blocking, warnings }
    throw error
  }
  return data
}

export const api = {
  get: (path, params) => {
    const qs = new URLSearchParams(
      Object.entries(params ?? {}).filter(([, v]) => v !== '' && v !== null && v !== undefined))
    return request('GET', qs.size ? `${path}?${qs}` : path)
  },
  post: (path, body) => request('POST', path, body),
  patch: (path, body) => request('PATCH', path, body),
}

export const STATUSES = {
  new: 'nouvelle', interesting: 'intéressante', applied: 'candidature envoyée',
  ghosted: 'sans réponse', ignored: 'écartée', rejected: 'refusée', interview: 'entretien',
}
export const DRAFT_STATUSES = {
  draft: 'à relire', deposited: 'dans Gmail', sent: 'envoyée', discarded: 'abandonnée',
}
export const REGIONS = { mdg: 'Madagascar', lille: 'Lille', remote: 'Télétravail', other: 'Autres' }
