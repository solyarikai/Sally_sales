import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const mainApp = path.resolve(__dirname, '../../frontend/src')
const mcpSrc = path.resolve(__dirname, 'src')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      // MCP overrides — intercept ALL relative import depths
      // ../api/client (1 level) and ../../api/client (2 levels)
      { find: /\.\.\/api\/client/, replacement: path.join(mcpSrc, 'api/client') },
      { find: /\.\.\/api$/, replacement: path.join(mcpSrc, 'api/index') },
      { find: /\.\.\/\.\.\/api$/, replacement: path.join(mcpSrc, 'api/index') },
      // Store override
      { find: /\.\.\/store\/appStore/, replacement: path.join(mcpSrc, 'store/appStore') },
      { find: /\.\.\/\.\.\/store\/appStore/, replacement: path.join(mcpSrc, 'store/appStore') },
      // Theme override — CRITICAL: filter components use ../../hooks/useTheme
      { find: /hooks\/useTheme/, replacement: path.join(mcpSrc, 'hooks/useTheme') },

      // @main alias — point to main app source for component reuse
      { find: '@main', replacement: mainApp },
    ],
  },
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8002',
      '/mcp': 'http://localhost:8002',
    },
  },
})
