const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
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

export const demoInspections = [
  { inspection_id: 'INSP-2408-0184', product: { name: 'Harvest Gold Basmati Rice', category: 'Food grains' }, compliance: { status: 'PASS', violations: [] }, created_at: '2026-08-24T09:18:00Z', fields: { manufacturer: 'Harvest Gold Foods', net_quantity: '5 kg', mrp: 'Rs. 640.00' }, visual_checks: { readability: 'PASS', font_height: 2.1, placement: 'PASS' } },
  { inspection_id: 'INSP-2408-0183', product: { name: 'Nectar Hand Wash', category: 'Personal care' }, compliance: { status: 'FAIL', violations: ['MRP declaration is missing', 'Consumer care details not found'] }, created_at: '2026-08-24T08:42:00Z', fields: { manufacturer: 'Nectar Homecare', net_quantity: '250 ml', mrp: null }, visual_checks: { readability: 'PASS', font_height: 1.4, placement: 'REVIEW' } },
  { inspection_id: 'INSP-2408-0182', product: { name: 'Kaveri Roasted Peanuts', category: 'Packaged food' }, compliance: { status: 'REVIEW', violations: ['Manufacture date could not be confidently read'] }, created_at: '2026-08-23T16:05:00Z', fields: { manufacturer: 'Kaveri Snacks', net_quantity: '200 g', mrp: 'Rs. 85.00' }, visual_checks: { readability: 'REVIEW', font_height: 1.1, placement: 'PASS' } },
  { inspection_id: 'INSP-2408-0181', product: { name: 'ClearShield Surface Cleaner', category: 'Household' }, compliance: { status: 'PASS', violations: [] }, created_at: '2026-08-23T14:26:00Z', fields: { manufacturer: 'ClearShield Labs', net_quantity: '500 ml', mrp: 'Rs. 129.00' }, visual_checks: { readability: 'PASS', font_height: 2.7, placement: 'PASS' } }
]
