# Contributing to atrophy

atrophy is a small, opinionated tool. Ideas, issues, and pull requests are all
welcome, and there is very little ceremony. If something feels off, or a metric
does not match how your day actually felt, that is useful: open an issue.

## How to help

- **Have an idea or found a bug?** Open an issue. Half-formed is fine.
- **Want to propose a metric?** Open an issue and say what it would measure and why.
  A good metric tracks how your day actually felt (the 1-5 rating), not just what is
  easy to count.
- **Sending a PR?** Go ahead, no need to ask first. Keep it focused. If you change
  logic, run the tests and keep them green:

  ```bash
  python3 tests/test_atrophy.py && python3 tests/test_atrophy_llm.py
  ```

## The one hard rule: keep it private

atrophy only ever works on aggregates, and nothing leaves the machine. So:

- No prompt, code, or client name should ever be persisted or printed.
- No personal data in the diff: no real names, no absolute /Users/ paths, no real
  project or client names (use placeholders like core-api or billing).

Install the anti-leak hook before your first commit and it will catch this for you:

```bash
printf '#!/usr/bin/env bash\nexec "$(git rev-parse --show-toplevel)/bin/check-no-leak.sh"\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## The spirit (nice to keep, not enforced)

- **Honest mirror, not a judge.** Indicative numbers, never moralizing. The user decides.
- **No score to game.** The tool stays silent unless something needs attention.
- **Stdlib first, minimal code.** Reach for a dependency only when a few lines will not do.

That is it. Thanks for caring about this.
