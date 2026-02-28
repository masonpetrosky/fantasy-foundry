FROM node:22-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src

ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_SUPABASE_PREFS_TABLE=user_preferences
ARG VITE_GA4_MEASUREMENT_ID
ARG VITE_SENTRY_DSN_FRONTEND
ARG VITE_FF_PREMIUM_ENABLED=0
ARG VITE_STRIPE_PUBLISHABLE_KEY
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_PREFS_TABLE=$VITE_SUPABASE_PREFS_TABLE
ENV VITE_GA4_MEASUREMENT_ID=$VITE_GA4_MEASUREMENT_ID
ENV VITE_SENTRY_DSN_FRONTEND=$VITE_SENTRY_DSN_FRONTEND
ENV VITE_FF_PREMIUM_ENABLED=$VITE_FF_PREMIUM_ENABLED
ENV VITE_STRIPE_PUBLISHABLE_KEY=$VITE_STRIPE_PUBLISHABLE_KEY

COPY frontend/public ./public

RUN npm run build


FROM python:3.12-slim

WORKDIR /app

ENV FF_CANONICAL_HOST=fantasy-foundry.com
ENV FF_ENV=production
ENV FF_CORS_ALLOW_ORIGINS=https://fantasy-foundry.com
ENV FF_PREWARM_DEFAULT_CALC=0
ENV FF_REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP=1
ENV FF_CALC_SYNC_RATE_LIMIT_PER_MINUTE=20
ENV FF_CALC_SYNC_AUTH_RATE_LIMIT_PER_MINUTE=60
ENV FF_CALC_JOB_CREATE_RATE_LIMIT_PER_MINUTE=10
ENV FF_CALC_JOB_CREATE_AUTH_RATE_LIMIT_PER_MINUTE=30
ENV FF_CALC_JOB_STATUS_RATE_LIMIT_PER_MINUTE=180
ENV FF_CALC_JOB_STATUS_AUTH_RATE_LIMIT_PER_MINUTE=360
ENV FF_PROJ_RATE_LIMIT_PER_MINUTE=90
ENV FF_EXPORT_RATE_LIMIT_PER_MINUTE=20
ENV FF_CALC_MAX_ACTIVE_JOBS_PER_IP=1
ENV FF_CALC_MAX_ACTIVE_JOBS_TOTAL=24
ENV FF_TRUST_X_FORWARDED_FOR=1
ENV FF_TRUSTED_PROXY_CIDRS=cloudflare

RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --system --no-create-home appuser

COPY backend ./backend
COPY frontend ./frontend
COPY data ./data
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
