import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Organizer module — internal server only, served publicly via dashboard proxy
// Public URL: http://localhost:3020/module/organizer
// Internal:   http://localhost:3022
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/module/organizer',
  server: {
    host: true,
    allowedHosts: true,
    port: 3022,
    // HMR: browser connects back via the PUBLIC dashboard port (3009),
    // which proxies /module/organizer WS back to this internal server.
    hmr: {
      clientPort: 3020,
    },
    proxy: {
      // REST API calls: /organizer/* → http://localhost:4040/organizer/*
      '/organizer': {
        target: 'http://localhost:4040',
        changeOrigin: true,
      },
    },
  },
})
