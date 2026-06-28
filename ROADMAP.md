# Roadmap

Where help is most wanted. atrophy is small on purpose, so this list stays focused on
making the existing metrics more honest rather than adding surface. See `CONTRIBUTING.md`
before opening a PR.

## Calibration (the real gap)
- **Calibrate alert thresholds on real data** ([#1](https://github.com/michel-is-coding/atrophy/issues/1)).
  Today's thresholds are first-pass guesses. A metric is only as good as its correlation to
  how the day actually felt (the 1-5 rating).
- **English detection.** The token sets are calibrated mostly on real French; the English
  pass is younger and needs tuning against real English transcripts.

## Better proxies
- **Persistence proxy, scoped properly** ([#2](https://github.com/michel-is-coding/atrophy/issues/2)).
- **gh pull requests as an output proxy** for the value axis ([#4](https://github.com/michel-is-coding/atrophy/issues/4)).

## Coverage
In priority order.

1. **Cross-platform: Linux and Windows** ([#6](https://github.com/michel-is-coding/atrophy/issues/6)). The first goal. The analysis core (reading
   transcripts, computing aggregates, the report) is already portable; only presence tracking
   and the launchd agents are macOS-bound. First step: a no-presence, report-on-demand mode
   that runs anywhere Python does. Native scheduling later: systemd timers on Linux, Task
   Scheduler on Windows.
2. **More AI tools** ([#3](https://github.com/michel-is-coding/atrophy/issues/3)): ChatGPT or
   Copilot used in the browser, not just Claude Code transcripts.

## Vision: from observing to improving (research)
atrophy today is layer one: make cognitive offloading visible so you can see your own autopilot.
Observation is not the end goal. The longer arc is to help you exercise and rebuild judgment,
not just watch it slip. That points at cognitive-forcing interventions: structuring the AI
interaction so you stay the one doing the thinking.

This is a research direction, not a committed feature. Some external work in this space:
- [The Forge Protocol](https://github.com/lorenzofamiglini/The-Forge-Protocol-Agent): instead of
  handing you answers, it asks Socratic questions, critiques your draft instead of rewriting it,
  makes you commit before seeing the model output (anti-anchoring), and runs periodic unassisted
  skill audits.
- [Epistemic Protocols](https://github.com/jongwony/epistemic-protocols): structured checkpoints
  at decision points that catch misalignment early, at the plan stage, before a wrong direction
  hardens into code and costs hours to undo.

There are surely others. If you know of work in this space, open an issue.

## Housekeeping
- Tag a first release (v0.1.0) so the tool can be cited by version.

## Out of scope, on purpose
- No score to optimize, no leaderboard, no streaks. The tool stays an honest mirror, not a game.
- No new dependency for what a few lines of standard library can do.
- Nothing that persists a prompt, code, or client name. Aggregates only, always.
