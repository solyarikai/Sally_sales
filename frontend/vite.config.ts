/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5179,
    strictPort: false,
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            const loc = proxyRes.headers['location'];
            if (loc && typeof loc === 'string') {
              proxyRes.headers['location'] = loc.replace(/^https?:\/\/[^/]+/, '');
            }
          });
        },
      },
    },
  },
  test: {
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})
