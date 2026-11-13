#!/usr/bin/env bash
# Publishes docs/spec/01-mvp-spec.md (#1) and docs/issues/*.md (#2..) to GitHub Issues via the REST API.
# Uses `gh api` (REST), which also works where GitHub GraphQL is unavailable.
set -euo pipefail
REPO="${REPO:-andrewromanchukk/black-eye}"
gh api "repos/$REPO/labels" -f name=ready-for-agent -f color=0E8A16 -f description="Ready to implement" >/dev/null 2>&1 || true

create() {  # $1 title, $2 body file
  python3 - "$1" "$2" <<'PY' | gh api "repos/$REPO/issues" --input - --jq '"#\(.number) \(.title)"'
import json, re, sys
title, path = sys.argv[1], sys.argv[2]
body = open(path, encoding="utf-8").read()
body = re.sub(r"#0(\d)\b", r"#\1", body)          # "#02" -> "#2" so GitHub links issues
body = body.replace("](../issues/)", "](https://github.com/" + __import__("os").environ.get("REPO", "andrewromanchukk/black-eye") + "/tree/dev/docs/issues)")
print(json.dumps({"title": title, "body": body, "labels": ["ready-for-agent"]}))
PY
}

create "MVP spec: Zapik — online booking for tire shops and workshops" docs/spec/01-mvp-spec.md
for f in docs/issues/*.md; do
  title=$(head -1 "$f" | sed -E 's/^# [0-9]+: //')
  create "$title" "$f"
done
