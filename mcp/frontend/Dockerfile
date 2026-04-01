FROM node:20-alpine AS builder

WORKDIR /app

# Copy MCP frontend first (for package.json)
COPY mcp/frontend/package.json mcp/frontend/package-lock.json* ./
RUN npm install

# Copy MCP frontend source
COPY mcp/frontend/ .

# Copy main app source INTO the app tree (so node_modules resolves)
COPY frontend/src ./main-app-src

# Fix the @main alias to point to copied main app source
RUN sed -i "s|path.resolve(__dirname, '../../frontend/src')|path.resolve(__dirname, 'main-app-src')|g" vite.config.ts

# Override main app's api/client.ts with MCP's version (so all @main components use MCP auth)
RUN cp src/api/client.ts main-app-src/api/client.ts

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY mcp/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
