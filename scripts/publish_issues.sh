#!/usr/bin/env bash
# Публікує специфікацію і тікети з docs/ у GitHub Issues (потрібен авторизований `gh`).
set -euo pipefail
gh label create ready-for-agent --color 0E8A16 --force >/dev/null
gh issue create --title "MVP spec: Zapik" --label ready-for-agent --body-file docs/spec/01-mvp-spec.md
for f in docs/issues/*.md; do
  title=$(head -1 "$f" | sed 's/^# //')
  gh issue create --title "$title" --label ready-for-agent --body-file "$f"
done
