FROM node:22-alpine AS build

WORKDIR /workspace
COPY . .
RUN cd ui && npm ci && npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/ui/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
