import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.PROD ? '/docs/api' : '/api',
  timeout: 300000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      const basePath = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
      const loginPath = `${basePath}/login` || '/login'
      if (window.location.pathname !== loginPath) {
        window.location.href = loginPath
      }
    }
    return Promise.reject(error)
  },
)

export default http
