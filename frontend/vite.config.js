import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/soil': 'http://localhost:8000',
      '/farmland': 'http://localhost:8000',
      '/quality': 'http://localhost:8000',
      '/crops-reccomendation': 'http://localhost:8000',
    }
  }
})