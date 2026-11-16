#!/bin/sh
# Container start-up. Local compose sets RUN_MIGRATIONS=1 and SEED_DEMO=1.
# In staging/production run migrations as a separate one-off task instead.
set -e

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "[entrypoint] applying migrations"
  python manage.py migrate --noinput
fi

if [ "${SEED_DEMO:-0}" = "1" ]; then
  echo "[entrypoint] loading demo data (idempotent)"
  python manage.py seed_demo
fi

exec "$@"
