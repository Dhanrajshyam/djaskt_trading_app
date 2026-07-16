import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Fixed port so it matches the CORS/URL guidance in the Django backend's
    // .env.example and this app's own .env comments.
    port: 5173,
  },
})
