import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vehicle module — internal server only, served publicly via dashboard proxy
// Public URL: http://localhost:3020/module/vehicle
// Internal:   http://localhost:3023
export default defineConfig({
  plugins: [react()],
  base: '/module/vehicle',
  server: {
    host: true,
    allowedHosts: true,
    port: 3023,
    hmr: {
      clientPort: 3020,
    },
    proxy: {
      '/api': {
        target: 'http://localhost:4040',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:4040',
        ws: true,
      },
    },
  },
})
