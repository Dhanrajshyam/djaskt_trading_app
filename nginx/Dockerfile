# syntax=docker/dockerfile:1

# Centralized nginx: serves the React frontend's static build directly and
# reverse-proxies /api and /ws to the Django backend, so the browser only
# ever talks to one origin. This is a standalone service, not bundled into
# the frontend's own image — see docker-compose.yml's `additional_contexts`
# wiring, which builds ../frontend/react's image first and hands this build
# its filesystem as the named context "frontend" below. Baking the built
# assets in at image-build time (rather than mounting a runtime volume)
# means there's no stale-output risk: every `docker compose build` rebuilds
# both images from source, in order.
FROM nginx:1.27-alpine

COPY --from=frontend /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
