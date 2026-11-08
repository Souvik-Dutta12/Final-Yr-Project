import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  // frontend/.env theke address pore (na thakle default use hobe)
  const env = loadEnv(mode, process.cwd(), '')
  const TS_SERVER = env.VITE_API_TARGET || 'http://127.0.0.1:8010' // TypeScript server
  const PY_SERVER = env.VITE_PY_TARGET || 'http://127.0.0.1:8000'  // Python server

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        // TS mode (VITE_API_MODE=ts)
        '/api': TS_SERVER,
        // Python mode (default) + land cover (dui mode e-i Python)
        '/soil': PY_SERVER,
        '/crops-reccomendation': PY_SERVER,
        '/analyze': PY_SERVER,
        '/change': PY_SERVER,
      },
    },
  }
})