#!/usr/bin/env bash
# Publish spec/ticket markdown files to GitHub Issues via the REST API (works where GraphQL is unavailable).
# Usage: scripts/publish_issues.sh docs/spec/17-pilot-readiness-spec.md docs/issues/18-*.md ...
# The first "# NN: Title" line becomes the issue title. Files are published in the given order.
set -euo pipefail
REPO="${REPO:-andrewromanchukk/black-eye}"
gh api "repos/$REPO/labels" -f name=ready-for-agent -f color=0E8A16 -f description="Ready to implement" >/dev/null 2>&1 || true
for f in "$@"; do
  python3 - "$f" "$REPO" <<'PY' | gh api "repos/$REPO/issues" --input - --jq '"#\(.number) \(.title)"'
import json, re, sys
path, repo = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
first, _, body = text.partition("\n")
title = re.sub(r"^#\s*(#?\d+\s*[—:-]\s*)?", "", first).strip()
body = re.sub(r"#0(\d)\b", r"#\1", body).replace("](../issues/)", f"](https://github.com/{repo}/tree/dev/docs/issues)")
print(json.dumps({"title": title, "body": body.strip(), "labels": ["ready-for-agent"]}))
PY
done
