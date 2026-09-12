import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API lives behind /api in every environment; only the dev/preview target
// changes. VITE_API_TARGET lets a second backend be pointed at without an edit.
const target = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'
const proxy = { '/api': { target, changeOrigin: false } }

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  // vite preview needs its own proxy declaration; without it every /api call
  // from a production build falls through to the SPA fallback and returns HTML.
  preview: { proxy },
})
