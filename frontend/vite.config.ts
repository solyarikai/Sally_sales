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
  build: {
    // Target modern browsers only — drops legacy polyfills
    target: 'es2020',
    rollupOptions: {
      output: {
        manualChunks: {
          // Core framework — cached across all pages
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // ag-grid — only loaded by ContactsPage, PipelinePage, QueryDashboardPage, AllProspectsPage
          'vendor-ag-grid': ['ag-grid-community', 'ag-grid-react'],
          // Markdown — only loaded by chat pages
          'vendor-markdown': ['react-markdown', 'remark-gfm'],
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
