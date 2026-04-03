import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const mainApp = path.resolve(__dirname, '../../frontend/src')
const mcpSrc = path.resolve(__dirname, 'src')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      // MCP overrides — intercept main app's relative imports at any depth
      // API client (MCP auth instead of X-Company-ID)
      { find: /\.\.\/api\/client/, replacement: path.join(mcpSrc, 'api/client') },
      { find: /\.\.\/\.\.\/api\/client/, replacement: path.join(mcpSrc, 'api/client') },
      // Catch ./client imports from INSIDE main app's api/ directory (e.g. replies.ts → ./client)
      { find: new RegExp(mainApp.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '/api/client'), replacement: path.join(mcpSrc, 'api/client') },
      { find: /^\.\.\/api$/, replacement: path.join(mcpSrc, 'api/index') },
      { find: /^\.\.\/\.\.\/api$/, replacement: path.join(mcpSrc, 'api/index') },
      // Store (MCP Zustand store)
      { find: /\.\.\/store\/appStore/, replacement: path.join(mcpSrc, 'store/appStore') },
      { find: /\.\.\/\.\.\/store\/appStore/, replacement: path.join(mcpSrc, 'store/appStore') },
      // Theme (MCP theme with mcp-theme localStorage key)
      // MUST match ../hooks/useTheme AND ../../hooks/useTheme (filter components are 2 levels deep)
      { find: /^\.\.\/hooks\/useTheme$/, replacement: path.join(mcpSrc, 'hooks/useTheme') },
      { find: /^\.\.\/\.\.\/hooks\/useTheme$/, replacement: path.join(mcpSrc, 'hooks/useTheme') },

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
