# ==========================================
# TraceGuard Frontend Production Dockerfile
# Milestone 7: Production Deployment & Containerization
# ==========================================

# Stage 1: Build the Vite production bundle
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests first for efficient layer caching
COPY package.json package-lock.json ./
RUN npm ci

# Copy source files
COPY . .

# Set API base URL to empty so requests use relative paths handled by Nginx proxy
ENV VITE_API_BASE_URL=""

# Build production bundle with TypeScript check
RUN npm run build

# Stage 2: Serve static bundle via lightweight Nginx
FROM nginx:alpine AS runner

# Remove default nginx template configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom Nginx configuration with reverse proxy and security headers
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled SPA static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

# Health check using lightweight wget built into alpine
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

# Start nginx daemon in foreground
CMD ["nginx", "-g", "daemon off;"]
