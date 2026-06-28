#!/usr/bin/env bash
# Refuses to commit any personal data / personal path. Runs as a pre-commit hook.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
staged=$(git diff --cached --name-only)
[ -z "$staged" ] && exit 0
# 1) no data file
if echo "$staged" | grep -qE '(^|/)(atrophy\.md|ratings\.log|presence\.log|projects\.tsv|last\.txt)$|alert-.*\.txt$'; then
  echo "x anti-leak: data file staged, remove it." >&2; exit 1
fi
# 2) no absolute home path (/Users/<someone>/...) in staged content. Generic (catches any
#    user, not a hardcoded name). The hook excludes itself: its own regex contains the
#    pattern, otherwise it would block on every edit.
if git diff --cached -- . ':(exclude)bin/check-no-leak.sh' \
     | grep -nE '/Users/[A-Za-z][A-Za-z0-9._-]*/' >&2; then
  echo "x anti-leak: absolute home path detected above (use \$HOME or ~)." >&2; exit 1
fi
echo "ok anti-leak"
