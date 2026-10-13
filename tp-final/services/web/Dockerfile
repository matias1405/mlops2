# Build context: tp-final/
FROM node@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build
WORKDIR /app
COPY services/web/package.json services/web/package-lock.json ./
RUN npm ci --no-audit --no-fund --loglevel=error
COPY services/web/ ./
RUN npm test && npm run build

# nginx sin privilegios (escucha en 8080). La config del ambiente se genera al arrancar desde
# /etc/nginx/templates (envsubst de la imagen oficial): misma imagen para dev y prod.
FROM nginxinc/nginx-unprivileged@sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6 AS runtime
# Parches de seguridad del sistema operativo (trivy); vuelve al usuario sin privilegios.
USER root
RUN apk upgrade --no-cache
USER 101
COPY --from=build /app/dist /usr/share/nginx/html
COPY services/web/nginx/templates /etc/nginx/templates
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10m --start-interval=5s --retries=5 CMD wget -qO /dev/null http://127.0.0.1:8080/config.json || exit 1
