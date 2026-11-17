# Zapik web/scheduler image, built FROM the golden base image (docker/base/Dockerfile).
#
# The base image is built/published manually (docs/registry-guide.md); this file never builds it.
# Where it comes from:
#   - docker compose up: BASE_IMAGE from the environment / .env, default zapik-base:local (built manually)
#   - plain docker build: docker build --build-arg BASE_IMAGE=<registry>/zapik-base:<tag>@sha256:<digest> .
# The base already pins OS, Python 3.13.18, pip and tini; here only app dependencies and code are added.
ARG BASE_IMAGE=zapik-base:local
FROM ${BASE_IMAGE}

COPY requirements.txt .
RUN pip install --require-hashes --no-deps -r requirements.txt && pip check

COPY . .
# collectstatic needs settings to load but never connects: dummy values, build-time only.
RUN DJANGO_SECRET_KEY=build DATABASE_URL=postgres://build@localhost/build python manage.py collectstatic --noinput \
    && chown -R app:app /app

USER app
EXPOSE 8000
ENTRYPOINT ["tini", "--", "sh", "docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
