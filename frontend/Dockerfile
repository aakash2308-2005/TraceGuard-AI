# syntax=docker/dockerfile:1

# ---- Build stage ----
FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json ./
# Use npm install (no lockfile committed in scaffold); produces node_modules.
RUN npm install

COPY . .
RUN npm run build

# ---- Runtime stage (nginx serves static build + proxies /api) ----
FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
