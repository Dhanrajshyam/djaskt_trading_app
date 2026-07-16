# syntax=docker/dockerfile:1

# Build-only image: produces /app/dist and nothing else. There is no CMD
# here and this image is never `docker compose up`'d directly — it exists
# solely so the centralized nginx service (../nginx/Dockerfile) can pull
# /app/dist out of it via Compose's `build.additional_contexts`. Keeping
# static-file serving out of this image (rather than bundling nginx here)
# is what lets nginx stay a single, independent, centralized service —
# today it reverse-proxies /api and /ws to Django and serves this build
# output directly; later it's also the natural place to add load
# balancing across multiple Django replicas, without touching this image.
FROM node:24-alpine AS build

WORKDIR /app

# Installed separately from the rest of the source so Docker's layer cache
# is reused across builds that only change application code, not
# dependencies — package-lock.json is committed, so `npm ci` (not
# `npm install`) gives a reproducible install from the exact locked tree.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build
