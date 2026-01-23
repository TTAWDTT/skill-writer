import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Let the browser set multipart boundaries automatically for FormData
    if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
      if (config.headers) {
        delete config.headers['Content-Type']
        delete config.headers['content-type']
      }
    } else {
      // Default JSON content-type for normal requests (avoid forcing it for FormData)
      if (config.headers && !config.headers['Content-Type'] && !config.headers['content-type']) {
        config.headers['Content-Type'] = 'application/json'
      }
    }

    // Add auth token if available
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('token')
    }
    return Promise.reject(error)
  }
)
