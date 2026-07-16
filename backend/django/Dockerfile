# syntax=docker/dockerfile:1

# --- Builder stage -----------------------------------------------------
# Installs dependencies into an isolated venv. All of this project's
# dependencies (psycopg[binary], argon2-cffi, cryptography via
# django-ninja-jwt[crypto]) ship as manylinux wheels, so no C compiler or
# dev headers are needed here — kept minimal on purpose.
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# --- Runtime stage -------------------------------------------------------
# Slim final image: only the installed venv + application code, run as a
# non-root user.
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=django_app.settings

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY . .

# Static assets (including django-ninja's bundled Swagger UI files, served
# via WhiteNoise) are collected at build time so the image is self-
# contained and needs no writable volume for them at runtime. Requires a
# SECRET_KEY to be resolvable — .env.example's fallback value is enough
# for collectstatic, which never touches the database or real secrets.
RUN SECRET_KEY=build-time-placeholder-not-used-at-runtime \
    python manage.py collectstatic --noinput

RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /app appuser \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

# UVICORN_WORKERS is overridable per-environment without rebuilding the image.
CMD ["sh", "-c", "uvicorn django_app.asgi:application --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4}"]
