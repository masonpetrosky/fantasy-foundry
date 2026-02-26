FROM node:22-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src

ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_SUPABASE_PREFS_TABLE=user_preferences
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_PREFS_TABLE=$VITE_SUPABASE_PREFS_TABLE

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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY data ./data
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
