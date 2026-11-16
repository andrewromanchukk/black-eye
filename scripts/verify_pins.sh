#!/usr/bin/env bash
# Checks that pinned image digests match what the registry serves for the pinned tags,
# and that requirements.txt is in sync with requirements.in. Run on a machine with Docker.
set -euo pipefail
cd "$(dirname "$0")/.."
fail=0
check() {  # $1 = "image:tag@sha256:..." as written in the repo
  local ref="$1" tag="${1%@*}" pinned="${1#*@}" actual
  actual=$(docker buildx imagetools inspect "$tag" --format '{{json .Manifest.Digest}}' | tr -d '"')
  if [ "$actual" = "$pinned" ]; then echo "OK    $tag"; else
    echo "DIFF  $tag  pinned=$pinned  registry=$actual  (tag was rebuilt; see docs/build-environment.md)"; fail=1; fi
}
check "$(sed -n 's/^FROM \(python:[^ ]*\).*/\1/p' Dockerfile)"
check "$(sed -n 's/^ *image: \(postgres:[^ ]*\).*/\1/p' docker-compose.yml)"
echo "Lock file:"
docker run --rm -v "$PWD:/src" -w /src "$(sed -n 's/^FROM \([^ ]*\).*/\1/p' Dockerfile)" sh -c \
  "pip install -q pip-tools && pip-compile --quiet --generate-hashes --strip-extras --no-emit-index-url \
   --output-file=/tmp/req.txt requirements.in && diff -q /tmp/req.txt requirements.txt" \
  && echo "OK    requirements.txt matches requirements.in" || { echo "DIFF  regenerate requirements.txt"; fail=1; }
exit $fail
