#!/usr/bin/env bash
# Samples system inactivity (presence) via launchd (io.atrophy.presence,
# StartInterval 60s). Appends 'epoch idle_secs focus' to ~/.atrophy/presence.log.
# atrophy cross-references this retroactively with run windows (transcripts) for
# "active monitoring during runs". 2a = idle only; 2b = terminal focus (boolean)
# to separate passive stillness from "stepped away". Aggregates only:
# no content stored, and the app name is NEVER persisted, only the boolean 0/1.
set -euo pipefail
# HIDIdleTime = nanoseconds since last keyboard/mouse event -> seconds. Note: no
# `exit` in awk -> it consumes the full ioreg stream (otherwise SIGPIPE 141 on ioreg);
# the `!f` flag keeps only the first occurrence.
idle=$(ioreg -c IOHIDSystem 2>/dev/null | awk '/HIDIdleTime/ && !f{print int($NF/1000000000); f=1}')

# Axis 2b: is the terminal (where the agent runs) in the foreground? -> 0/1 ONLY.
# The app name is read into memory then discarded; only the boolean is written.
front=$(lsappinfo info -only name "$(lsappinfo front 2>/dev/null)" 2>/dev/null \
        | sed -n 's/.*"LSDisplayName"="\(.*\)"/\1/p')
case "$front" in
  Ghostty|Terminal|iTerm2|iTerm|Alacritty|kitty|WezTerm|Warp|Hyper|tmux \
  |Code|"Visual Studio Code"|Cursor|Windsurf) focus=1 ;;
  *) focus=0 ;;
esac

printf '%s %s %s\n' "$(date +%s)" "${idle:-0}" "$focus" >> "${ATROPHY_HOME:-$HOME/.atrophy}/presence.log"
