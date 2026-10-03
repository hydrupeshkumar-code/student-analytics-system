# ---------- 1. build the React frontend
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Python API that also serves the built SPA
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd --create-home --uid 10001 saap \
 && mkdir -p /app/backend/ml_models /app/backend/data \
 && chown -R saap /app/backend/ml_models /app/backend/data \
 && chmod +x /app/backend/start.sh
USER saap
EXPOSE 8000
# Safe defaults; the host's environment variables (e.g. Render's DATABASE_URL) override these.
ENV PORT=8000 \
    ENVIRONMENT=production \
    DATABASE_URL=sqlite:////app/backend/data/saap.db
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health').status==200 else 1)"
# validate config -> migrate -> first-run bootstrap (admin / optional demo data) -> serve on $PORT
CMD ["./start.sh"]
