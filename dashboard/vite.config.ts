import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://open-pc-desktop:8080',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://open-pc-desktop:8080',
        ws: true
      }
    }
  }
})