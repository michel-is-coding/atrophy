#!/usr/bin/env bash
set -euo pipefail
UID_NUM="$(id -u)"; LA="$HOME/Library/LaunchAgents"
for name in presence daily watch; do
  launchctl bootout "gui/$UID_NUM/io.atrophy.$name" 2>/dev/null || true
  rm -f "$LA/io.atrophy.$name.plist"
done
echo "✓ agents removed."
read -r -p "Also delete your data (~/.atrophy)? [y/N] " a
{ [ "${a:-N}" = "y" ] || [ "${a:-N}" = "Y" ]; } && rm -rf "$HOME/.atrophy" && echo "→ data deleted." || echo "→ data kept."
