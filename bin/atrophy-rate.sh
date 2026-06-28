#!/usr/bin/env bash
# Ground-truth mini-command (axis 1): log your "deliberate judgment today: 1-5".
# Usage: atrophy-rate 4   (1=autopilot / 5=fully engaged). Replaces today's rating.
# Stores a number only in ~/.atrophy/ratings.log, never free text.
exec python3 "$(dirname "$0")/../atrophy.py" --rate "${1:?usage: atrophy-rate.sh <N>  (N from 1 to 5, e.g.: 4)}"
