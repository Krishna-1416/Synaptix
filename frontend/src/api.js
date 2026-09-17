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

export async function compressImageForInspection(file, maxDimension = 1800, quality = 0.88) {
  if (!file || !file.type || !file.type.startsWith('image/')) return file
  // If file is already reasonably sized (< 1.2 MB), skip canvas re-encoding
  if (file.size < 1.2 * 1024 * 1024) return file

  return new Promise((resolve) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      if (width <= maxDimension && height <= maxDimension && file.size < 2 * 1024 * 1024) {
        return resolve(file)
      }

      if (width > height) {
        if (width > maxDimension) {
          height = Math.round((height * maxDimension) / width)
          width = maxDimension
        }
      } else {
        if (height > maxDimension) {
          width = Math.round((width * maxDimension) / height)
          height = maxDimension
        }
      }

      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, width, height)

      canvas.toBlob(
        (blob) => {
          if (!blob || blob.size >= file.size) {
            resolve(file)
          } else {
            const compressedFile = new File([blob], file.name.replace(/\.[^/.]+$/, "") + ".jpg", {
              type: 'image/jpeg',
              lastModified: Date.now()
            })
            resolve(compressedFile)
          }
        },
        'image/jpeg',
        quality
      )
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(file)
    }
    img.src = url
  })
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
  startGoogleLogin: async (redirectTo, role) => {
    const params = new URLSearchParams()
    if (redirectTo) params.set('redirect_to', redirectTo)
    if (role) params.set('role', role)
    const query = params.toString() ? `?${params.toString()}` : ''
    return (await request(`/api/auth/google${query}`)).json()
  },
  exchangeCode: async (code, role) => {
    const params = new URLSearchParams({ code })
    if (role) params.set('role', role)
    return (await request(`/api/auth/exchange?${params.toString()}`)).json()
  },
  updateRole: async (role) => (await request('/api/auth/role', {
    method: 'POST',
    body: JSON.stringify({ role })
  })).json(),
  getDashboardStats: async () => (await request('/api/dashboard/stats')).json(),
  getInspections: async ({ page = 1, limit = 10, status = '', search = '', inspectorId = '' } = {}) => {
    const params = new URLSearchParams({ page, limit })
    if (status) params.set('status', status)
    if (search) params.set('search', search)
    if (inspectorId) params.set('inspector_id', inspectorId)
    return (await request(`/api/inspections?${params}`)).json()
  },
  getInspection: async (id) => (await request(`/api/inspections/${encodeURIComponent(id)}`)).json(),
  inspect: async ({ file, productName, category }) => {
    const optimizedFile = await compressImageForInspection(file)
    const formData = new FormData()
    formData.append('file', optimizedFile)
    if (productName) formData.append('product_name', productName)
    if (category) formData.append('category', category)
    return (await request('/api/inspect', { method: 'POST', body: formData })).json()
  },
  inspectBatch: async ({ files, productName, category }) => {
    const optimizedFiles = await Promise.all((files || []).map((f) => compressImageForInspection(f)))
    const formData = new FormData()
    optimizedFiles.forEach((file) => formData.append('files', file))
    if (productName) formData.append('product_name', productName)
    if (category) formData.append('category', category)
    return (await request('/api/inspect/batch', { method: 'POST', body: formData })).json()
  },
  inspectMultiAngle: async ({ files, productName, category }) => {
    const optimizedFiles = await Promise.all((files || []).map((f) => compressImageForInspection(f)))
    const formData = new FormData()
    optimizedFiles.forEach((file) => formData.append('files', file))
    if (productName) formData.append('product_name', productName)
    if (category) formData.append('category', category)
    return (await request('/api/inspect/multi-angle', { method: 'POST', body: formData })).json()
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
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 4000)
  }
}

