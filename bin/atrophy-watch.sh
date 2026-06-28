#!/usr/bin/env bash
# REAL-TIME guard (hourly via launchd io.atrophy.watch). Notifies when a
# daily threshold is crossed: active time too high, unbounded window, rating dropping.
# Reuses `atrophy.py --notify-line` (lightweight path, no git). Anti-spam:
# one notification per distinct MESSAGE per day (sentinel ~/.atrophy/alert-DATE.txt),
# so a crossed threshold does not re-ping every hour. No score pushed (anti-Goodhart).
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
AH="${ATROPHY_HOME:-$HOME/.atrophy}"
SENT="$AH/alert-$(date +%F).txt"

notify() { osascript -e "display notification \"${1//\"/}\" with title \"Atrophy\"" 2>/dev/null || true; }

MSG="$(python3 "$DIR/atrophy.py" --notify-line 2>/dev/null || true)"
[ -z "$MSG" ] && exit 0
# already notified this exact message today? -> silence
[ -f "$SENT" ] && grep -qxF "$MSG" "$SENT" && exit 0
notify "$MSG"                          # MSG already includes the alert prefix
printf '%s\n' "$MSG" >> "$SENT"
