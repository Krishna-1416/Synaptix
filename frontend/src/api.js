const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export function resolveApiUrl(path) {
  if (!path) return null
  return /^https?:\/\//i.test(path) ? path : `${API_BASE_URL}${path}`
}

async function request(path, options = {}) {
  const token = window.localStorage.getItem('synaptix_access_token')
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: 'no-store',
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || payload.error || `Request failed (${response.status})`)
  }

  return response
}

export const api = {
  login: async ({ email, password }) => (await request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  })).json(),
  signup: async ({ email, password, fullName, role }) => (await request('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name: fullName, role })
  })).json(),
  getCurrentUser: async () => (await request('/api/auth/me')).json(),
  startGoogleLogin: async () => (await request('/api/auth/google')).json(),
  getDashboardStats: async () => (await request('/api/dashboard/stats')).json(),
  getInspections: async ({ page = 1, limit = 10, status = '', search = '' } = {}) => {
    const params = new URLSearchParams({ page, limit })
    if (status) params.set('status', status)
    if (search) params.set('search', search)
    return (await request(`/api/inspections?${params}`)).json()
  },
  getInspection: async (id) => (await request(`/api/inspections/${encodeURIComponent(id)}`)).json(),
  inspect: async ({ file, productName, category }) => {
    const formData = new FormData()
    formData.append('file', file)
    if (productName) formData.append('product_name', productName)
    if (category) formData.append('category', category)
    return (await request('/api/inspect', { method: 'POST', body: formData })).json()
  },
  updateInspection: async (id, payload) => (await request(`/api/inspections/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })).json(),
  downloadReport: async (id) => {
    const response = await request(`/api/report/${encodeURIComponent(id)}`)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `Compliance_Certificate_${id}.pdf`
    anchor.click()
    URL.revokeObjectURL(url)
  }
}

