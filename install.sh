#!/usr/bin/env bash
# Atrophy installer (macOS). Registers the 3 launchd agents at your paths and guides LLM opt-in.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
AH="$HOME/.atrophy"
UID_NUM="$(id -u)"
LA="$HOME/Library/LaunchAgents"

[ "$(uname)" = "Darwin" ] || { echo "✗ macOS required."; exit 1; }
command -v python3 >/dev/null || { echo "✗ Python 3 required."; exit 1; }

mkdir -p "$AH" "$LA"
echo "→ data: $AH"

for name in presence daily watch; do
  tpl="$DIR/launchd/io.atrophy.$name.plist.template"
  out="$LA/io.atrophy.$name.plist"
  sed -e "s#@ATROPHY_DIR@#$DIR#g" -e "s#@HOME@#$HOME#g" "$tpl" > "$out"
  launchctl bootout "gui/$UID_NUM/io.atrophy.$name" 2>/dev/null || true
  # tolerant bootstrap + retry: on re-run the async unload may not be done yet
  # (race bootout->bootstrap); we don't let a failure abort the loop (set -e).
  launchctl bootstrap "gui/$UID_NUM" "$out" 2>/dev/null \
    || { sleep 1; launchctl bootstrap "gui/$UID_NUM" "$out" 2>/dev/null || true; }
  echo "→ agent io.atrophy.$name installed"
done

echo
# grep -c reads the full stream (grep -q would close the pipe early -> SIGPIPE from launchctl under
# pipefail -> spurious warning). `|| true`: grep exits 1 on zero matches.
n=$(launchctl list | grep -c io.atrophy || true)
[ "${n:-0}" -ge 1 ] && echo "✓ $n agents active" || echo "⚠ check 'launchctl list | grep atrophy'"
echo "→ log your judgment each evening: $DIR/bin/atrophy-rate.sh <N>   (N from 1 to 5, e.g.: 4)"
echo "→ report on demand:               python3 $DIR/atrophy.py"

echo
read -r -p "Show how to enable the local LLM lens (optional)? [y/N] " ans
if [ "${ans:-N}" = "y" ] || [ "${ans:-N}" = "Y" ]; then
  echo "→ Manual setup (nothing is downloaded automatically):"
  echo "   1. brew install llama.cpp"
  echo "   2. place a GGUF model in ~/models/ (e.g. gemma-3-4b-it-Q4_K_M.gguf, ~3 GB)"
  echo "   3. run: python3 $DIR/atrophy.py --llm   (or --llm-model <path.gguf>)"
  echo "   Without this, the core still runs (the lens degrades gracefully)."
else
  echo "→ LLM skipped (the core runs without it; the code degrades gracefully)."
fi
echo "✓ installed."
