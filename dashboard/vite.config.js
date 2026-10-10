import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Central Dashboard — THE single public frontend port for the entire platform.
// All module traffic is routed through here.
//
// Port layout (only these two are user-visible):
//   FRONTEND (this server) : 3009   → http://localhost:3020
//   BACKEND               : 8009   → http://localhost:4040
//
// Internal Vite servers (not user-visible):
//   Social module          : 3010   (FRONTEND + 1)
//   Organizer module       : 3011   (FRONTEND + 2)
//
// Path routing:
//   /module/social/*       → Social Module internal Vite  (3010)
//   /module/organizer/*    → Organizer Module internal Vite (3011)
//   /api/*                 → Unified Backend API (8009)
//   /organizer/*           → Organizer API routes on backend (8009)
//   /ws, /ws/*             → Backend WebSocket hub (8009)
//   /                      → This dashboard app

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: true,
    port: 3020,
    open: true,
    proxy: {
      // ── Module UIs (proxy to internal Vite dev servers) ────────
      '/module/social': {
        target: 'http://localhost:3021',
        changeOrigin: true,
        ws: true,   // Also proxy Vite HMR WebSocket for this sub-app
      },
      '/module/organizer': {
        target: 'http://localhost:3022',
        changeOrigin: true,
        ws: true,
      },
      '/module/vehicle': {
        target: 'http://localhost:3023',
        changeOrigin: true,
        ws: true,
      },
      // ── Backend API (social module routes) ─────────────────────
      '/api': {
        target: 'http://localhost:4040',
        changeOrigin: true,
      },
      // ── Backend API (organizer module routes) ──────────────────
      '/organizer': {
        target: 'http://localhost:4040',
        changeOrigin: true,
        ws: true,   // Organizer WebSocket (/organizer/ws)
      },
      // ── Backend WebSocket hub ──────────────────────────────────
      '/ws': {
        target: 'http://localhost:4040',
        ws: true,
      },
      // Face thumbnails — proxy to backend so /faces/<img> resolves correctly
      '/faces': {
        target: 'http://localhost:4040',
        changeOrigin: true,
      },
    },
  },
})
