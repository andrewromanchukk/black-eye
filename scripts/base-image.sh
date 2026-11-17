#!/usr/bin/env bash
# Build / publish the Zapik golden base image (docker/base/Dockerfile).
#
#   scripts/base-image.sh build            # local image zapik-base:local (current arch)
#   scripts/base-image.sh push             # multi-arch (amd64+arm64) build & push to ECR, prints the digest
#
# push needs: AWS CLI logged in, Docker buildx, and
#   AWS_ACCOUNT_ID=123456789012 AWS_REGION=eu-central-1 [ECR_REPO=zapik-base]
# Tags are immutable-style: py3.13.18-trixie-YYYYMMDD-<git sha>. Consumers pin the printed digest.
set -euo pipefail
cd "$(dirname "$0")/.."

PY_TAG=$(sed -n 's/^ARG PYTHON_IMAGE=python:\([^@]*\)@.*/\1/p' docker/base/Dockerfile)   # 3.13.18-slim-trixie
VERSION="py${PY_TAG%%-*}-trixie-$(date +%Y%m%d)-$(git rev-parse --short HEAD)"

case "${1:-}" in
  build)
    docker build --build-arg BASE_VERSION="$VERSION" -t zapik-base:local docker/base
    echo "Built zapik-base:local ($VERSION)"
    ;;
  push)
    : "${AWS_ACCOUNT_ID:?set AWS_ACCOUNT_ID}" "${AWS_REGION:?set AWS_REGION}"
    REPO="${ECR_REPO:-zapik-base}"
    REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    aws ecr describe-repositories --repository-names "$REPO" --region "$AWS_REGION" >/dev/null 2>&1 \
      || aws ecr create-repository --repository-name "$REPO" --region "$AWS_REGION" \
           --image-tag-mutability IMMUTABLE --image-scanning-configuration scanOnPush=true >/dev/null
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
    docker buildx build --platform linux/amd64,linux/arm64 \
      --build-arg BASE_VERSION="$VERSION" \
      -t "${REGISTRY}/${REPO}:${VERSION}" --push docker/base
    DIGEST=$(docker buildx imagetools inspect "${REGISTRY}/${REPO}:${VERSION}" --format '{{json .Manifest.Digest}}' | tr -d '"')
    echo
    echo "Pushed ${REGISTRY}/${REPO}:${VERSION}"
    echo "Pin this in app builds:"
    echo "  BASE_IMAGE=${REGISTRY}/${REPO}@${DIGEST}"
    ;;
  *)
    echo "usage: $0 build|push" >&2; exit 2 ;;
esac
