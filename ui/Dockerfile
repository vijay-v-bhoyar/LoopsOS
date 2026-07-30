FROM node:22-alpine AS build

WORKDIR /workspace
ENV LOOPOS_USE_CHECKED_IN_DATA=1
COPY . .
RUN cd ui && npm ci && npm run build

FROM nginxinc/nginx-unprivileged:1.31.3-alpine3.24@sha256:59ccf0943b0b8e8d9e6ea9039a39555730f544701a655c596f7df7d096c593f5 AS runtime

COPY ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/ui/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
