#!/usr/bin/env bash
# Build / publish the Zapik application image (./Dockerfile) on top of the golden base image.
#
#   BASE_IMAGE=<registry>/zapik-base@sha256:<digest> scripts/app-image.sh build   # local image zapik-web:<git sha>
#   BASE_IMAGE=<registry>/zapik-base@sha256:<digest> scripts/app-image.sh push    # multi-arch build & push to ECR
#
# push needs: AWS CLI logged in, Docker buildx, AWS_ACCOUNT_ID, AWS_REGION [, ECR_REPO=zapik-web]
# Tag = git commit sha (immutable); the script refuses to build from a dirty working tree.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${BASE_IMAGE:?set BASE_IMAGE=<registry>/zapik-base@sha256:<digest> (always by digest)}"
case "$BASE_IMAGE" in *@sha256:*) ;; *) echo "BASE_IMAGE must be pinned by digest (…@sha256:…)" >&2; exit 2 ;; esac
if [ -n "$(git status --porcelain)" ]; then echo "Working tree is dirty: commit first, the tag is the git sha" >&2; exit 2; fi
TAG=$(git rev-parse --short=12 HEAD)

case "${1:-}" in
  build)
    docker build --build-arg BASE_IMAGE="$BASE_IMAGE" -t "zapik-web:${TAG}" .
    echo "Built zapik-web:${TAG}"
    ;;
  push)
    : "${AWS_ACCOUNT_ID:?set AWS_ACCOUNT_ID}" "${AWS_REGION:?set AWS_REGION}"
    REPO="${ECR_REPO:-zapik-web}"
    REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    aws ecr describe-repositories --repository-names "$REPO" --region "$AWS_REGION" >/dev/null 2>&1 \
      || aws ecr create-repository --repository-name "$REPO" --region "$AWS_REGION" \
           --image-tag-mutability IMMUTABLE --image-scanning-configuration scanOnPush=true >/dev/null
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
    docker buildx build --platform linux/amd64,linux/arm64 \
      --build-arg BASE_IMAGE="$BASE_IMAGE" \
      --label org.opencontainers.image.revision="$(git rev-parse HEAD)" \
      -t "${REGISTRY}/${REPO}:${TAG}" --push .
    DIGEST=$(docker buildx imagetools inspect "${REGISTRY}/${REPO}:${TAG}" --format '{{json .Manifest.Digest}}' | tr -d '"')
    echo
    echo "Pushed ${REGISTRY}/${REPO}:${TAG}"
    echo "Deploy by digest:"
    echo "  ${REGISTRY}/${REPO}@${DIGEST}"
    ;;
  *)
    echo "usage: BASE_IMAGE=…@sha256:… $0 build|push" >&2; exit 2 ;;
esac
