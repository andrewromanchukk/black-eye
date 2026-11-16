# Zapik golden base image
# =======================
# Shared, pinned runtime for every Zapik Python service. Built and patched centrally,
# pushed to ECR, and consumed by app images by digest (see docs/base-image.md).
#
# Contains: Debian 13 (trixie) + Python 3.13.18 (official image, by digest),
#           pinned pip, tini as PID 1, non-root user `app` (uid/gid 10001), /app workdir.
# Does NOT contain: application code or Python dependencies (those belong to the app image).
#
# Every input is pinned. To update, change an ARG, rebuild, test, push, bump the digest
# in the app build. Do not run `apt-get upgrade` here: it makes builds non-reproducible.

# python:3.13.18-slim-trixie, multi-arch index digest, checked 2026-11-16
ARG PYTHON_IMAGE=python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
FROM ${PYTHON_IMAGE}
# re-declare: ARGs before FROM are not visible after it (used in the base.name label)
ARG PYTHON_IMAGE

# Pinned versions (Debian trixie, checked 2026-11-16 via api.ftp-master.debian.org/madison)
ARG PIP_VERSION=26.3
ARG TINI_VERSION=0.19.0-3+b8
ARG APP_UID=10001
ARG BASE_VERSION=dev

LABEL org.opencontainers.image.title="zapik-base" \
      org.opencontainers.image.description="Pinned Python runtime for Zapik services" \
      org.opencontainers.image.source="https://github.com/andrewromanchukk/black-eye" \
      org.opencontainers.image.version="${BASE_VERSION}" \
      org.opencontainers.image.base.name="${PYTHON_IMAGE}" \
      com.zapik.python.version="3.13.18" \
      com.zapik.pip.version="${PIP_VERSION}" \
      com.zapik.tini.version="${TINI_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    LANG=C.UTF-8

# OS packages: only what the runtime needs on top of the official slim image
# (which already ships ca-certificates, netbase, tzdata). Every package pinned to an exact version.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends "tini=${TINI_VERSION}"; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    tini --version

RUN python -m pip install "pip==${PIP_VERSION}" && pip --version

# Fixed uid/gid so file ownership is identical on every host and in ECS
RUN groupadd --system --gid "${APP_UID}" app \
    && useradd --system --uid "${APP_UID}" --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app && chown app:app /app

WORKDIR /app

# tini reaps zombies and forwards SIGTERM, so ECS/Docker stop the app cleanly.
# The image stays root so app images can install packages; app images end with `USER app`.
ENTRYPOINT ["tini", "--"]
