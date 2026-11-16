# Pinned build environment — every build gets the same OS, Python and packages.
#   - base image: exact Python patch + Debian release + immutable digest
#   - pip: exact version
#   - Python packages: requirements.txt is a lock file with hashes (--require-hashes)
#   - OS packages: none installed; if you add any, pin versions (apt-get install pkg=VERSION)
# How to update pins: docs/build-environment.md

# python:3.13.18-slim-trixie (Debian 13), multi-arch index digest, checked 2026-11-16
FROM python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

ARG PIP_VERSION=26.3
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

RUN python -m pip install "pip==${PIP_VERSION}"
COPY requirements.txt .
RUN pip install --require-hashes --no-deps -r requirements.txt && pip check

COPY . .
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput \
    && chown -R app:app /app

USER app
EXPOSE 8000
ENTRYPOINT ["sh", "docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
