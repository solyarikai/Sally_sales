import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const mainApp = path.resolve(__dirname, '../../frontend/src')
const mcpSrc = path.resolve(__dirname, 'src')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      // MCP overrides — these take priority over @main
      // When main app components import '../api/client', resolve to MCP's client (with MCP auth)
      { find: /^\.\.\/api\/client$/, replacement: path.join(mcpSrc, 'api/client') },
      { find: /^\.\.\/api$/, replacement: path.join(mcpSrc, 'api/index') },
      { find: /^\.\.\/store\/appStore$/, replacement: path.join(mcpSrc, 'store/appStore') },

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
