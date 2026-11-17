#!/usr/bin/env bash
# Local build of the golden base image (docker/base/Dockerfile) -> zapik-base:local.
# Builds only on this machine. It does NOT create registry repositories and does NOT push anything.
set -euo pipefail
cd "$(dirname "$0")/.."

PY_TAG=$(sed -n 's/^ARG PYTHON_IMAGE=python:\([^@]*\)@.*/\1/p' docker/base/Dockerfile)   # 3.13.18-slim-trixie
VERSION="py${PY_TAG%%-*}-trixie-$(date +%Y%m%d)-$(git rev-parse --short HEAD)"

docker build --build-arg BASE_VERSION="$VERSION" -t zapik-base:local docker/base
echo "Built zapik-base:local ($VERSION)"
