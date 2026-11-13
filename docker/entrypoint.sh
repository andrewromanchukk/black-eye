#!/bin/sh
set -e
# Local/dev convenience. In staging/production run migrations as a separate one-off task.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi
exec "$@"
