const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

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

export const demoInspections = [
  {
    inspection_id: 'SYN-DEMO-1042', user_id: 'demo-user', created_at: '2026-09-10T10:30:00+05:30',
    product: { name: 'Harvest Gold Rice', category: 'Food & beverage' },
    fields: { generic_name: 'Basmati rice', net_quantity: '1 kg', mrp: '₹145.00', manufacturer: 'Harvest Gold Foods Pvt. Ltd.' },
    visual_checks: { readability: 'Clear', font_height: 1.5, placement: 'Compliant' },
    compliance: { status: 'PASS', score: 0.96, confidence: 0.94, violations: [] },
    rules_obeyed: ['Product name declaration', 'Net quantity declaration', 'MRP declaration', 'Manufacturer details'], rules_not_obeyed: []
  },
  {
    inspection_id: 'SYN-DEMO-1039', user_id: 'demo-user', created_at: '2026-09-09T14:15:00+05:30',
    product: { name: 'FreshSip Mango Drink', category: 'Food & beverage' },
    fields: { generic_name: 'Mango beverage', net_quantity: '750 ml', mrp: '₹80.00', manufacturer: 'FreshSip Beverages' },
    visual_checks: { readability: 'Clear', font_height: 1.2, placement: 'Compliant' },
    compliance: { status: 'FAIL', score: 0.78, confidence: 0.92, violations: ['Expiry date missing', 'Required declaration unreadable'] },
    rules_obeyed: ['Product name declaration', 'Net quantity declaration', 'MRP declaration'], rules_not_obeyed: [{ rule: 'Expiry date declaration', reason: 'No readable expiry date was detected.' }, { rule: 'Required declaration readability', reason: 'One mandatory declaration could not be read clearly.' }]
  },
  {
    inspection_id: 'SYN-DEMO-1035', user_id: 'demo-user', created_at: '2026-09-08T11:05:00+05:30',
    product: { name: 'PureCare Handwash', category: 'Personal care' },
    fields: { generic_name: 'Liquid handwash', net_quantity: '250 ml', mrp: '₹110.00' },
    visual_checks: { readability: 'Fair', font_height: 0.9, placement: 'Review needed' },
    compliance: { status: 'REVIEW', score: 0.68, confidence: 0.81, violations: ['Manufacturer address needs review'] },
    rules_obeyed: ['Product name declaration', 'Net quantity declaration', 'MRP declaration'], rules_not_obeyed: [{ rule: 'Manufacturer details', reason: 'Address text requires manual confirmation.' }]
  },
  {
    inspection_id: 'SYN-DEMO-1028', user_id: 'admin-demo', created_at: '2026-09-07T09:20:00+05:30',
    product: { name: 'HomeBright Detergent', category: 'Household' },
    fields: { generic_name: 'Detergent powder', net_quantity: '2 kg', mrp: '₹215.00', manufacturer: 'HomeBright Consumer Products' },
    visual_checks: { readability: 'Clear', font_height: 1.3, placement: 'Compliant' },
    compliance: { status: 'PASS', score: 0.93, confidence: 0.9, violations: [] },
    rules_obeyed: ['Product name declaration', 'Net quantity declaration', 'MRP declaration', 'Manufacturer details'], rules_not_obeyed: []
  }
]

