# syntax=docker/dockerfile:1
# Two-stage build: compile the Vite SPA, then serve it with nginx and reverse-proxy
# /api → the gateway (mirroring the dev Vite proxy: strip /api, inject the bearer token,
# stream SSE unbuffered). Referenced by docker-compose.yml's `frontend` service.

# --- Stage 1: build the static SPA -----------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
# Install deps from the lockfile first for a cached layer.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- Stage 2: serve dist + proxy /api → gateway ----------------------------
FROM nginx:1.27-alpine
# nginx config is a template: GATEWAY_TARGET / GATEWAY_TOKEN are substituted at start
# by the stock nginx entrypoint's envsubst step (our wrapper reads the token secret).
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint-hachi.sh
RUN chmod +x /docker-entrypoint-hachi.sh && rm -f /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173
ENTRYPOINT ["/docker-entrypoint-hachi.sh"]
CMD ["nginx", "-g", "daemon off;"]
