FROM node:20-alpine AS builder

WORKDIR /app

# Copy main app source (for @main alias reuse)
COPY frontend/src /main-app-src

# Copy MCP frontend
COPY mcp/frontend/package.json mcp/frontend/package-lock.json* ./
RUN npm install

COPY mcp/frontend/ .

# Fix the @main alias to point to copied main app source
RUN sed -i "s|../../frontend/src|/main-app-src|g" vite.config.ts

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY mcp/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
