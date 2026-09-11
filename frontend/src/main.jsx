import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

if ('serviceWorker' in navigator) {
  if (import.meta.env.DEV || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    // Unregister stale dev service workers and flush caches so live edits never get trapped in old caches
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      for (const registration of registrations) {
        registration.unregister()
      }
    })
    if ('caches' in window) {
      caches.keys().then((names) => {
        for (const name of names) {
          caches.delete(name)
        }
      })
    }
  } else {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}))
  }
}
