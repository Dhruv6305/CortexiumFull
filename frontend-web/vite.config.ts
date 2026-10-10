import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Social module — internal server only, served publicly via dashboard proxy
// Public URL: http://localhost:3020/module/social
// Internal:   http://localhost:3021
export default defineConfig({
  plugins: [react()],
  base: '/module/social',
  server: {
    host: true,
    allowedHosts: true,
    port: 3021,
    // HMR: browser connects back via the PUBLIC dashboard port (3009),
    // which proxies /module/social WS back to this internal server.
    hmr: {
      clientPort: 3020,
    },
    proxy: {
      // Keep direct access working too (API + WS)
      '/api': {
        target: 'http://localhost:4040',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:4040',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:4040',
        ws: true,
      },
      // Face thumbnails — proxy so /faces/<img> resolves to the backend
      '/faces': {
        target: 'http://localhost:4040',
        changeOrigin: true,
      },
    },
  },
});
