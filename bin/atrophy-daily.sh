#!/usr/bin/env bash
# Daily auto-run of atrophy, launched by launchd (io.atrophy.daily, ~23:30).
# Appends the day's log and sends a macOS notification with the fordism headline. Additive: does not touch
# the real-time stack (notify.sh/statusline/mc). See
# docs/superpowers/plans/2026-06-28-atrophy-tracker-v1.md (section 8.2 deferred auto-run).
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

DIR="$(cd "$(dirname "$0")/.." && pwd)"
AH="${ATROPHY_HOME:-$HOME/.atrophy}"
LAST="$AH/last.txt"   # last full report, human-readable

notify() { osascript -e "display notification \"${1//\"/}\" with title \"Atrophy\"" 2>/dev/null || true; }

# Catch-up: machine off/asleep at 23:30 means missed days. replace-by-date
# makes recalculation safe -> backfill the last 3 days from transcripts.
# Gaps heal as soon as the machine runs at least once every 3 days.
for d in 1 2 3; do
  day=$(date -v-"${d}"d +%F 2>/dev/null) \
    && python3 "$DIR/atrophy.py" --date "$day" >/dev/null 2>&1 || true
done

if ! OUT="$(python3 "$DIR/atrophy.py" 2>&1)"; then
  notify "daily run failed, see ~/.atrophy/cron.log"
  printf '%s\n' "$OUT" >&2
  exit 1
fi

printf '%s\n' "$OUT" > "$LAST"

# cap presence.log growth (60s poller = ~1440 lines/day): keep ~3 days.
P="$AH/presence.log"
[ -f "$P" ] && tail -n 5000 "$P" > "$P.tmp" && mv -f "$P.tmp" "$P" || true
# purge alert sentinels older than 7 days (1 small file/day).
find "$AH" -maxdepth 1 -name 'alert-*.txt' -mtime +7 -delete 2>/dev/null || true

# Axis 2: silent except on alert (anti-Goodhart). The end-of-day summary goes through
# the SAME guard as the hourly agent (atrophy-watch.sh, deduplicated): no double notification,
# one alert per distinct message per day. The full report stays on demand
# (~/.atrophy/last.txt); no score is pushed.
bash "$DIR/bin/atrophy-watch.sh" || true

# Ground-truth reminder (axis 1): ask for today's rating IF not yet given. This is
# NOT a metric push (no score shown), it is an INPUT entry, the felt sense
# that validates the measurement; therefore compatible with anti-Goodhart. 1 dialog/day max, conditional,
# `giving up after` to never block the cron, robust to cancellation.
RATINGS="$AH/ratings.log"
if ! grep -q "^$(date +%F) " "$RATINGS" 2>/dev/null; then
  ANS="$(osascript -e 'tell application "System Events" to text returned of (display dialog "Atrophy: how deliberate was your thinking today? (1 = autopilot · 5 = fully engaged)" default answer "" with title "Daily rating" buttons {"Later", "Rate"} default button "Rate" giving up after 120)' 2>/dev/null || true)"
  case "$ANS" in
    [1-5]) python3 "$DIR/atrophy.py" --rate "$ANS" >/dev/null 2>&1 || true ;;
  esac
fi
exit 0
