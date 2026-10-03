#!/bin/sh
# Container entrypoint: validate configuration, migrate, bootstrap, serve.
set -e

case "${DATABASE_URL}" in
  sqlite*)
    echo "WARNING: DATABASE_URL is not set to a server database — using SQLite at ${DATABASE_URL#sqlite:///}."
    echo "WARNING: on Render (and most container hosts) this file is wiped on every deploy/restart."
    echo "WARNING: deploy with the render.yaml Blueprint, or set DATABASE_URL to a PostgreSQL/MySQL URL."
    ;;
esac

if [ -z "${JWT_SECRET}" ]; then
  # one secret shared by all workers in this container; sessions reset when the container restarts
  JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
  export JWT_SECRET
  echo "WARNING: JWT_SECRET is not set — generated a temporary one. Set JWT_SECRET so sign-ins survive restarts."
fi

alembic upgrade head
python -m app.cli bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers --forwarded-allow-ips='*'
