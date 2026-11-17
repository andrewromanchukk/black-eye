# Zapik web/scheduler image, built FROM the golden base image (docker/base/Dockerfile).
#
# Where the base comes from:
#   - local `docker compose up`: compose builds docker/base and passes it in as build context "base"
#   - production / ECR:  docker build --build-arg BASE_IMAGE=<account>.dkr.ecr.<region>.amazonaws.com/zapik-base@sha256:<digest> .
#   - plain local build:  docker build -t zapik-base:local docker/base && docker build --build-arg BASE_IMAGE=zapik-base:local .
# The base already pins OS, Python 3.13.18, pip and tini; here only app dependencies and code are added.
ARG BASE_IMAGE=base
FROM ${BASE_IMAGE}

COPY requirements.txt .
RUN pip install --require-hashes --no-deps -r requirements.txt && pip check

COPY . .
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput \
    && chown -R app:app /app

USER app
EXPOSE 8000
ENTRYPOINT ["tini", "--", "sh", "docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
