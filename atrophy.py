#!/usr/bin/env python3
"""Atrophy: track-record of fordism & active time from Claude Code transcripts.
Lean v1: read-only, stdlib only, zero network, aggregates-only (never raw).
See docs/superpowers/specs/2026-06-28-usage-behavior-tracking-design.md (§8.1).

================================ REASON FOR BEING (mindset) ==============================
Why this tool exists. Re-read when tempted to "optimize" it.

1. MIRROR, NOT JUDGE. The tool is for SEEING yourself, not scoring yourself. Goodhart's
   law: "when a measure becomes a target, it ceases to be a good measure". The moment you
   try to push fordism% down, you PERFORM engagement instead of creating it (padding your
   prompts, no longer saying "ok"): the number improves, the behavior does not, the mirror
   lies. Hence the design: silent (no score to stare at) + capacity framing (celebrate what
   is held, don't induce guilt).
2. THE SCARCE ASSET IS NOT TIME, IT IS JUDGMENT. AI makes execution nearly free; the
   bottleneck shifts to WHAT to do and WHY. Delegating execution = healthy; delegating
   strategic judgment = selling the asset that produces the value. Fordism measures this
   slippage.
3. FEELING PRODUCTIVE ≠ PRODUCING. "Robots are working for me" is process dopamine, not
   value delivered. Measuring the cost (hours, presence) without the value (axis 4:
   business%, commits) = lying to yourself with precision. 18h of runtime ≠ revenue.
4. CLOSING > ACCUMULATING. The cost is not the screen but the open loop (Zeigarnik, cf.
   _ALERT_ACTIVE_H). A closed session beats a 14h loop.
5. ATROPHY IS A FAILURE TO USE, NOT A FATALITY. A skill stays alive if you EXERCISE it.
   The tool prevents nothing: it makes things visible, the decision stays human.
6. THE END GOAL = BEING ABLE TO THROW IT AWAY. A weaning tool, not a crutch: internalize
   the reflex (exercise your judgment deliberately), then no longer need it. Measuring your
   behavior must not become yet another delegation (delegating self-observation).
7. EFFICIENCY = SUBTRACTION. Wealth/expansion does not come from more hours or more agents,
   but from better decisions on fewer fronts. "Less, but better judged."
8. OBSERVING IS LAYER 1, NOT THE GOAL. Making the offloading visible (this tool) is only the
   first step: understanding your own autopilot. The horizon is to help you EXERCISE and rebuild
   judgment, not just watch it slip, via cognitive-forcing interventions (commit before you see
   the answer, critique instead of rewrite, periodic unassisted audits). The decision stays
   human throughout. See ROADMAP.md, "Vision", for research directions.
======================================================================================="""
import os
import re
import sys
import json
import argparse
import statistics
import subprocess
from datetime import datetime, timedelta, date
from collections import defaultdict
from pathlib import Path


def parse_ts(s):
    """ISO8601 ('...Z') -> aware datetime, converted to local timezone."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone()  # local tz


def project_of(cwd):
    """Basename of the working dir; '?' if empty."""
    base = os.path.basename((cwd or "").rstrip("/"))
    return base or "?"


# --- Axis 4: value / output. v1 measures the COST (effort, time, presence) but zero of
# the VALUE produced. We tag business vs personal (distinguishes "18h of infra/personal"
# from "client revenue") and add free output proxies (the day's git commits).
# Privacy: tag + COUNTS only, never a persisted message/diff/filename.
# ponytail: the heuristic + the map = calibration knobs; gh PRs deferred (network).
_BUSINESS_HINT = re.compile(r"(crm|client|solar)", re.I)


def classify_project(name, overrides=None):
    """'business' or 'perso'. Exact override (local map) > heuristic on the name."""
    if overrides and name in overrides:
        return overrides[name]
    return "business" if _BUSINESS_HINT.search(name or "") else "perso"


def read_project_kinds(path):
    """Reads the local map 'project<TAB>business|perso' (# lines ignored). {} if absent."""
    p = Path(path)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].strip() in ("business", "perso"):
            out[parts[0].strip()] = parts[1].strip()
    return out


def resolve_repo(name, base=None):
    """Git repo path for a project basename: ~/code/<name> or ~/code/*/<name>
    (one level). None if not found / not a repo. ponytail: one level is enough here."""
    base = Path(base or os.environ.get("ATROPHY_REPO_BASE",
                                       os.path.join(os.path.expanduser("~"), "code")))
    direct = base / name
    if (direct / ".git").exists():
        return direct
    try:
        for parent in base.iterdir():
            cand = parent / name
            if (cand / ".git").exists():
                return cand
    except OSError:
        pass
    return None


def git_commits_on(repo_path, day):
    """Number of commits dated to the day in the repo = free output proxy.
    Read-only, count only (never a message). 0 if not a repo / error / timeout."""
    if not (Path(repo_path) / ".git").exists():
        return 0
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_path), "log", "--oneline",
             f"--since={day.isoformat()} 00:00:00",
             f"--until={day.isoformat()} 23:59:59"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return 0
    return len(r.stdout.splitlines()) if r.returncode == 0 else 0


def value_summary(rows):
    """Aggregates a day's value axis: total commits + share of active time on
    business projects (business% = revenue vs infra/personal)."""
    commits = sum(r.get("commits", 0) for r in rows)
    total_active = sum(r.get("active_sec", 0) for r in rows)
    biz_active = sum(r.get("active_sec", 0) for r in rows if r.get("kind") == "business")
    return {
        "commits": commits,
        "business_pct": (biz_active / total_active * 100) if total_active else 0.0,
    }


def gap_split(timestamps, threshold_sec):
    """Sum of inter-event gaps strictly below threshold_sec = active seconds.
    Gaps >= threshold are treated as idle (away) and dropped.
    # ponytail: default 10min threshold = calibration knob (RescueTime=5,
    # Wakapi=10, WakaTime=15). Recalibrate if active/span looks off."""
    ts = sorted(timestamps)
    active = 0.0
    for a, b in zip(ts, ts[1:]):
        d = (b - a).total_seconds()
        if d < threshold_sec:
            active += d
    return active


# Fordism = a prompt with low judgment input (rubber-stamping). Three families
# calibrated on real data (2026-06-28):
#   (a) pure acceptance/continuation  (b) DELEGATION of judgment  (c) CLOSURE.
# Design choice: wide net (over-count rather than miss); accept-token + short
# instruction = full fordism (Q2). Acknowledged LIMITATION: delegation is really
# fordism only on a STRATEGIC topic (not purely technical), a distinction not visible
# from text alone, resolved by the deferred topic-aware local LLM (spec §4.3).
# ponytail: bilingual (FR+EN). The English tokens are a first pass, not yet calibrated on
# real English data the way the French ones are (issue #5), tune as data comes in.
_ACCEPT_EXACT = {
    "ok", "oui", "ouais", "yes", "y", "go", "go go", "ok go", "vas-y", "vas y",
    "continue", "continu", "next", "suivant", "parfait", "ok parfait", "nickel",
    "ça marche", "ca marche", "valide", "validé", "ok merci", "merci", "ok go go",
    "👍", "✅", "🆗", "ok parfait merci", "super", "top", "cool", "bien",
    # English:
    "thanks", "thx", "thank you", "perfect", "great", "nice", "sounds good", "lgtm",
    "sure", "yep", "yeah", "done", "good", "looks good", "ok thanks", "great thanks",
}
_ACCEPT_PREFIX = re.compile(
    r"^(ok|oui|ouais|go|vas[- ]?y|next|suivant|continue?|continu|parfait|yes|nickel|valide"
    r"|sure|yeah|yep|perfect|great|thanks|thx|done|lgtm|sounds)\b")
# Delegation of judgment = the purest fordism ("you decide for me").
_DELEGATE = re.compile(
    r"(fais (ce que tu|au mieux|comme tu|ce qui te|le mieux|pour le mieux)"
    r"|comme tu (veux|le sens|préfères|l'entends)"
    r"|à toi de (voir|juger|décider)|je te fais confiance|comme bon te semble"
    r"|fais ce qui (te semble|est) (bon|mieux|bien)"
    r"|do what you (think|want|prefer|like)|your call|up to you"
    r"|whatever you (think|want|prefer)|you (decide|choose)|i trust you"
    r"|as you (see fit|wish|prefer)|do your best)")
# Closure / acknowledgment without verification.
_CLOSURE = re.compile(
    r"(c'?est bon|tout est bon|on a (fini|terminé)|ça (me )?suffit|ça suffit"
    r"|rien d'autre|ça ira|c'?est (parfait|nickel|ok|bon ça)"
    r"|we'?re done|that'?s (it|all|enough|good)|all good|nothing else"
    r"|good enough|ship it|looks good|lgtm)")
# SYNTHETIC markers injected by the harness (NOT typed prompts), to exclude
# from the prompt count (otherwise they inflate the denominator of the fordism ratio).
_SYNTHETIC = re.compile(
    r"^(\[request interrupted|<task-notification|<command-(name|message|args)"
    r"|<local-command|caveat: the messages below|<system-reminder)", re.I)

# ponytail: thresholds = calibration knobs (calibrated on real data 2026-06-28).
_FORDISME_LEN = 30        # accept-token + instruction shorter than this = fordism
_SUBSTANTIVE_LEN = 70     # beyond this, the prompt carries content -> never fordism


def is_accept_prompt(text):
    """True if the prompt is fordism (low judgment input): acceptance,
    delegation, or closure. Calibrated on real data, see the block above."""
    t = (text or "").strip().lower()
    if not t:
        return False
    # a long prompt carries content (correction, spec, reasoning) -> engagement,
    # not fordism. Guard against _DELEGATE/_CLOSURE false positives (.search).
    if len(t) > _SUBSTANTIVE_LEN:
        return False
    if t in _ACCEPT_EXACT:
        return True
    if _DELEGATE.search(t):          # delegation of judgment
        return True
    if _CLOSURE.search(t):           # closure / acknowledgment
        return True
    # accept-token + short = full fordism even with an instruction (Q2 choice).
    if _ACCEPT_PREFIX.match(t) and len(t) <= _FORDISME_LEN:
        return True
    return False


def fordisme_ratio(user_texts):
    """(accept_count, total_substantive, ratio). Empty prompts ignored."""
    texts = [t for t in user_texts if (t or "").strip()]
    total = len(texts)
    accept = sum(1 for t in texts if is_accept_prompt(t))
    return accept, total, (accept / total if total else 0.0)


def substantive_prompts(events):
    """The day's SUBSTANTIVE user prompts (len > _SUBSTANTIVE_LEN): those that
    carry a topic => input to the topic-aware local LLM classifier (axis 5b). The text
    stays transient (never persisted); only aggregated labels come out."""
    return [e["text"] for e in events
            if e["role"] == "user" and len((e["text"] or "").strip()) > _SUBSTANTIVE_LEN]


def _content_text(message):
    """Extract plain text from a transcript message.content (str or list of blocks)."""
    if not isinstance(message, dict):
        return ""
    c = message.get("content", "")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)
    return ""


def _output_chars(message):
    """PRODUCTION size of a message = text + tool-call payload (the agent's REAL
    work: Edit/Write code, Bash commands). On the user side, tool_result blocks
    (injected tool output, not typed) are excluded -> only what YOU wrote remains.
    Length only, never the content (privacy). Feeds the offloading proxy (#1) and the
    output size for review-before-accept."""
    if not isinstance(message, dict):
        return 0
    c = message.get("content", "")
    if isinstance(c, str):
        return len(c)
    if not isinstance(c, list):
        return 0
    total = 0
    for b in c:
        if isinstance(b, str):
            total += len(b)
        elif isinstance(b, dict):
            t = b.get("type")
            if t == "text":
                total += len(b.get("text", ""))
            elif t == "tool_use":   # code/command produced by the agent
                total += len(json.dumps(b.get("input", {}), ensure_ascii=False))
            # tool_result (user) = injected, not typed -> excluded
    return total


def iter_session_events(path):
    """Yield {ts, project, role, text} for user/assistant entries of one JSONL file."""
    try:
        fh = open(path, "r", encoding="utf-8")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except (ValueError, TypeError):
                continue
            if o.get("type") not in ("user", "assistant"):
                continue
            ts_raw = o.get("timestamp")
            if not ts_raw:
                continue
            try:
                ts = parse_ts(ts_raw)
            except (ValueError, TypeError):
                continue
            text = _content_text(o.get("message"))
            # interruption marker injected by the harness = not a typed prompt:
            # keep the event (for timing) but empty text (excluded from the fordism count).
            if _SYNTHETIC.match(text.strip()):
                text = ""
            yield {
                "ts": ts,
                "project": project_of(o.get("cwd", "")),
                "role": o.get("type"),
                "text": text,
                "out_chars": _output_chars(o.get("message")),
                "session": o.get("sessionId", ""),
            }


def scan(root, start_date, end_date):
    """Scan root/*/*.jsonl once; return {local_date: [event,...]} within [start,end]."""
    by_date = defaultdict(list)
    for path in Path(root).glob("*/*.jsonl"):
        for ev in iter_session_events(path):
            d = ev["ts"].date()
            if start_date <= d <= end_date:
                by_date[d].append(ev)
    return dict(by_date)


def aggregate_day(events, threshold_sec, overrides=None, day=None, repo_base=None):
    """Group a day's events by project -> one aggregates-only row each.
    NB: persists numbers + project name only, never prompt/code text (privacy §5).
    overrides/day/repo_base (axis 4): tag business/perso + the day's commits (output
    proxy). commits computed only if `day` is provided (else 0, no disk access)."""
    by_proj = defaultdict(list)
    for ev in events:
        by_proj[ev["project"]].append(ev)
    rows = []
    for project, evs in sorted(by_proj.items()):
        ts = [e["ts"] for e in evs]
        active = gap_split(ts, threshold_sec)
        span = (max(ts) - min(ts)).total_seconds() if len(ts) >= 2 else 0.0
        user_texts = [e["text"] for e in evs if e["role"] == "user"]
        accept, total, ratio = fordisme_ratio(user_texts)
        repo = resolve_repo(project, repo_base) if day else None
        rows.append({
            "project": project,
            "active_sec": active,
            "span_sec": span,
            "focus": (active / span) if span > 0 else 0.0,
            "prompts": total,
            "accept": accept,
            "fordisme": ratio,
            "kind": classify_project(project, overrides),
            "commits": git_commits_on(repo, day) if repo else 0,
        })
    return rows


def day_fordisme(events):
    """Overall fordism ratio for one day (all projects pooled)."""
    user_texts = [e["text"] for e in events if e["role"] == "user"]
    _, _, ratio = fordisme_ratio(user_texts)
    return ratio


# --- Review before accepting (2026 research finding). Fordism looks at WHAT you
# type; it does not say whether you READ before accepting. Yet the empirical core of
# over-reliance = accepting without checking (RCT N=1222, 2026; cognitive forcing
# functions). 100% local proxy from the timestamps: "ok" 4s after 300 lines =
# could not have read = blind acceptance. Complements fordism, does not replace it.
# ponytail: thresholds = calibration knobs.
_BLIND_MIN_LEN = 500       # agent output >= 500 chars = big enough to deserve a review
_BLIND_MAX_LAT = 15        # accepted in <=15s = too fast to have read it


def accept_latencies(events):
    """For each ACCEPTANCE prompt that directly follows an agent turn, returns
    (latency_sec, turn_output_size). The latency = time between the turn's end and your
    "ok" = your review time. Per session, in order."""
    by_sess = defaultdict(list)
    for e in events:
        by_sess[e.get("session", "")].append(e)
    out = []
    for evs in by_sess.values():
        turn_len, last_asst_ts = 0, None
        for e in sorted(evs, key=lambda x: x["ts"]):
            if e["role"] == "assistant":
                turn_len += e.get("out_chars", len(e.get("text") or ""))
                last_asst_ts = e["ts"]
            else:  # user: closes the previous turn
                if last_asst_ts is not None and is_accept_prompt(e["text"]):
                    out.append(((e["ts"] - last_asst_ts).total_seconds(), turn_len))
                turn_len, last_asst_ts = 0, None
    return out


def blind_accepts(latencies, min_len=_BLIND_MIN_LEN, max_latency=_BLIND_MAX_LAT):
    """(blind, eligible): among the acceptances that followed a BIG enough output
    (>= min_len), how many were granted too fast (0 <= latency <= max_latency)
    to have been read. Negative latency (clock skew) ignored."""
    eligible = [(lat, n) for lat, n in latencies if n >= min_len]
    blind = sum(1 for lat, _ in eligible if 0 <= lat <= max_latency)
    return blind, len(eligible)


def median_review_sec(latencies, min_len=_BLIND_MIN_LEN):
    """Median review delay (#3) over big outputs (>= min_len) = how much time
    you generally take before accepting. None if no big output was accepted."""
    vals = [lat for lat, n in latencies if n >= min_len and lat >= 0]
    return statistics.median(vals) if vals else None   # latencies already float


# --- Finding #1: volumetric delegation ratio. How much the agent PRODUCES (prose +
# tool-call code/commands, via _output_chars) per character YOU write: the higher it
# is, the more execution is delegated. INSPIRED by the "Offloading Score" (arXiv
# 2605.29392) but it is a volumetric proxy, not the exact counterfactual measure.
# INDICATIVE/trend, never a target (Goodhart). Lengths only, never the content.
def offloading_ratio(events):
    """(chars_agent, chars_you, ratio). chars_agent = the agent's total production
    (text + tool-call code); chars_you = what you typed. ratio = agent/you
    (0 if you typed nothing -> no division by zero)."""
    def sz(e):
        return e.get("out_chars", len(e.get("text") or ""))
    asst = sum(sz(e) for e in events if e["role"] == "assistant")
    usr = sum(sz(e) for e in events if e["role"] == "user")
    return asst, usr, (asst / usr if usr else 0.0)


# --- Finding #2: challenge / doubt ratio. The ONLY substantiated counter-measure to
# over-reliance = forcing yourself to doubt (cognitive forcing functions, Buçinça 2021).
# Here we MEASURE whether you practice it: prompts where you verify/contest/ask for
# justification = ACTIVE judgment (capacity framing, axis 3), the positive complement
# of fordism. ponytail: tokens chosen for PRECISION (a false positive inflates the
# "good" behavior = worse than a false negative). Word boundaries on prouve/challenge
# (else approuve/...); no bare `pourquoi`/`explique`/`critique`/`plutôt` (narrative FPs:
# "je t'explique", "chemin critique", "fais plutôt X"). We prefer to under-count.
_CHALLENGE = re.compile(
    r"(v[eé]rifie|re-?teste|relis|double[- ]?check|es[- ]?tu s[ûu]r|t'?es s[ûu]r"
    r"|tu es s[ûu]r|vraiment\s*\?|\bprouve|montre[- ]?moi|et si "
    r"|au contraire|non,?\s*plut[ôo]t|pas d'accord|je ne suis pas"
    r"|quels? risques?|cas limite|edge case|\bchallenge"
    r"|are you sure|you sure|\bverify\b|prove it|show me|really\s*\?|what if"
    r"|i disagree|not sure|reconsider|are you certain|is (that|this) (right|correct)"
    r"|what (are|about) the risks?)", re.I)


def is_challenge(text):
    """True if the prompt contests/verifies/asks for justification (active judgment)."""
    t = (text or "").strip()
    return bool(t) and _CHALLENGE.search(t) is not None


def challenge_ratio(user_texts):
    """(challenge_count, total_substantive, ratio). Empty prompts ignored."""
    texts = [t for t in user_texts if (t or "").strip()]
    total = len(texts)
    c = sum(1 for t in texts if is_challenge(t))
    return c, total, (c / total if total else 0.0)


def rolling(day_vals, end_date, n):
    """Mean of per-day fordism values over the last n days (inclusive of end_date).
    Days with no activity are absent from day_vals and excluded from the mean."""
    start = end_date - timedelta(days=n - 1)
    vals = [v for d, v in day_vals.items() if start <= d <= end_date]
    return sum(vals) / len(vals) if vals else 0.0


# --- Axis 1: ground truth. Daily self-rating "judgment exercised: 1-5",
# stored outside the repo, then correlated with the computed metrics. Scientific guard:
# if the felt sense does not correlate with fordism%, the metric is theater (spec axis 1).
_RATING_ROW = re.compile(r"^(\d{4}-\d\d-\d\d)\s+([1-5])\s*$")


def read_ratings(path):
    """Reads the ratings log 'YYYY-MM-DD N' -> {date: int 1-5}. Tolerates empty/absent."""
    p = Path(path)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        m = _RATING_ROW.match(line.strip())
        if m:
            try:   # the regex validates the FORM, not calendar validity (2026-13-40)
                out[date.fromisoformat(m.group(1))] = int(m.group(2))
            except ValueError:   # one hand-edited line must not kill the report
                continue
    return out


def record_rating(path, day, n):
    """Records/REPLACES the day's rating (1-5). replace-by-date like the table.
    Stores numbers only (never free text), aggregates privacy."""
    if not (isinstance(n, int) and 1 <= n <= 5):
        raise ValueError(f"rating out of 1-5: {n!r}")
    ratings = read_ratings(path)
    ratings[day] = n
    body = "".join(f"{d.isoformat()} {ratings[d]}\n" for d in sorted(ratings))
    Path(path).write_text(body, encoding="utf-8")


def pearson(xs, ys):
    """Pearson correlation coefficient (stdlib). None if <2 points or zero variance
    (undefined correlation), avoids a silent division by zero."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs)
    sy = sum((y - my) ** 2 for y in ys)
    if sx == 0 or sy == 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / (sx * sy) ** 0.5


def correlate_rating(ratings, judgement_by_day):
    """(r, n): correlates the felt rating (1-5) with the measured judgment exercised
    (=1-fordism) over the common days. r>0 = the metric matches experience (validated);
    r≈0 or <0 = theater signal. n = number of common days (None if <2)."""
    days = sorted(set(ratings) & set(judgement_by_day))
    xs = [ratings[d] for d in days]
    ys = [judgement_by_day[d] for d in days]
    return pearson(xs, ys), len(days)


# --- Axis 2: silent except for alerts. A daily "look at me" notification nudges you to
# game the metric (perform engagement). We switch to a rare, meaningful PUSH:
# alert only when a threshold is crossed; the report stays available on
# demand (atrophy-last.txt). Reduces the observer effect (anti-Goodhart, spec axis 2).
# ponytail: thresholds = calibration knobs.
_ALERT_FORD_DRIFT = 0.15   # +15 pts of fordism vs 30d baseline = clear drift
_ALERT_FORD_FLOOR = 0.40   # ...and at least 40% today (else = low-level noise)
_ALERT_FORD_MIN_PROMPTS = 12  # ...over enough prompts (anti intra-day morning noise)
_ALERT_WINDOW_H = 18       # mental window >= 18h = boundary-less day (separate signal)
_ALERT_ACTIVE_H = 10       # active time >= 10h = "too much used today". Why:
# Zeigarnik effect, an unfinished task occupies working memory; as long as a session
# is not finished it runs in the background in your head, hence the dopamine to go check.
# The cost is not the screen-hours but the open loop -> we alert on the day's volume.


def alert_message(today_ford, t30, window_sec=None, active_sec=None, prompts=None):
    """Returns the alert text ONLY if a threshold is crossed, else None.
    Independent triggers: judgment dropping, boundary-less day, active time too
    high. `prompts` (if provided) gates judgment drift below a minimum sample size
    -> avoids intra-day noise when the hourly agent checks in the morning (3 'ok' = 100%).
    Capacity wording (axis 3): JUDGMENT EXERCISED (=1-fordism), not deficit vocabulary;
    render_alert only adds the indicative prefix. ponytail: all thresholds = knobs."""
    alerts = []
    enough = (prompts is None) or (prompts >= _ALERT_FORD_MIN_PROMPTS)
    if enough and today_ford >= _ALERT_FORD_FLOOR and today_ford > t30 + _ALERT_FORD_DRIFT:
        alerts.append(f"judgment exercised dropped to {(1-today_ford)*100:.0f}% "
                      f"(30d baseline {(1-t30)*100:.0f}%)")
    if active_sec and active_sec >= _ALERT_ACTIVE_H * 3600:
        alerts.append(f"active time {_hms(active_sec)} today "
                      f"(beyond ~{_ALERT_ACTIVE_H}h, judgment tires)")
    if window_sec and window_sec >= _ALERT_WINDOW_H * 3600:
        alerts.append(f"mental window {_hms(window_sec)} (boundary-less day)")
    return " ; ".join(alerts) if alerts else None


_LOG_HEADER = (
    "# Atrophy: behavior track-record (aggregates only, never raw)\n\n"
    "| date | mental_window | agent_run | monitoring% | fordism% | active | projects | commits | business% | blind | challenge% | deleg× |\n"
    "|------|---------------|-----------|-------------|----------|--------|----------|---------|-----------|-------|------------|--------|\n"
)


def _fmt_summary_row(date, s):
    # Columns appended at the END of the row across versions -> back-compat for older
    # rows (missing columns = empty cells). challenge%/deleg× = research findings.
    return (f"| {date.isoformat()} | {s['fenetre']} | {s['run']} | "
            f"{s['monitoring_pct']} | {s['fordisme_pct']} | {s['actif']} | {s['projets']} | "
            f"{s.get('commits', 0)} | {s.get('business_pct', 0)} | {s.get('aveugle', 0)} | "
            f"{s.get('challenge_pct', 0)} | {s.get('deleg_x', 0)} |")


_DATA_ROW = re.compile(r"^\|\s*\d{4}-\d\d-\d\d\s*\|")


def log_day(path, date, summary):
    """Writes/REPLACES the day's summary row (1 row/day) in the Markdown
    table, and keeps the rows sorted by date. Replace-by-date: re-running during
    the day REFRESHES the row instead of duplicating it (and fixes a row computed
    too early / before calibration). Safe for backfilling past days."""
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    marker = f"| {date.isoformat()} |"
    rows = [ln for ln in lines if _DATA_ROW.match(ln) and not ln.startswith(marker)]
    rows.append(_fmt_summary_row(date, summary))
    rows.sort(key=lambda ln: ln.split("|")[1].strip())  # ISO date -> chronological sort
    # header always canonical (_LOG_HEADER) -> columns aligned even after evolution.
    body = _LOG_HEADER.rstrip("\n") + "\n" + "\n".join(rows) + "\n"
    path.write_text(body, encoding="utf-8")


def _hms(seconds):
    h, m = divmod(int(seconds) // 60, 60)
    return f"{h}h{m:02d}" if h else f"{m}min"


_SPARK = "▁▂▃▄▅▆▇█"


def _clamp01(f):
    return 0.0 if f < 0 else 1.0 if f > 1 else f


def _bar(frac, width=20):
    """Proportional bar: filled blocks for `frac` (0..1), dim blocks for the rest."""
    n = round(_clamp01(frac) * width)
    return "█" * n + "░" * (width - n)


def _spark(fracs):
    """One block char per value (0..1), low to high."""
    return "".join(_SPARK[round(_clamp01(f) * 7)] for f in fracs)


def render_truth_line(rating, correlation, min_days=5):
    """'ground truth' line (axis 1): the day's felt rating + correlation with experience
    once there are enough days. None if there's nothing to say yet."""
    r, n = correlation if correlation else (None, 0)
    bits = []
    if rating is not None:
        bits.append(f"today's rating: {rating}/5")
    if n >= min_days and r is not None:
        verdict = ("matches your experience ✓" if r >= 0.3 else
                   "decorrelated, metric needs review ⚠" if r <= 0 else "weak")
        bits.append(f"felt-vs-measured correlation: r={r:+.2f} over {n}d ({verdict})")
    elif n >= min_days:   # enough days but r undefined = zero variance (same ratings)
        bits.append(f"correlation undefined over {n}d (vary your ratings to reveal it)")
    elif rating is not None or n > 0:
        bits.append(f"correlation: will populate ({n}/{min_days} days rated)")
    return ("ground truth: " + " ; ".join(bits)) if bits else None


def render_report(date, rows, t7, t30, envelope=None, supervision=None,
                  rating=None, correlation=None, llm_breakdown=None, review=None,
                  review_median=None, challenge=None, offloading=None, spark=None):
    """Human terminal report. Headline = today's judgment vs trend (honest mirror).
    Bars and a trend sparkline make it glanceable; the data is unchanged."""
    total_prompts = sum(r["prompts"] for r in rows)
    total_accept = sum(r["accept"] for r in rows)
    today_ford = (total_accept / total_prompts) if total_prompts else 0.0
    total_active = sum(r["active_sec"] for r in rows)
    # Axis 3, capacity framing (not deficit): JUDGMENT EXERCISED (=1-fordism), growth not atrophy.
    today_judg, j7, j30 = 1 - today_ford, 1 - t7, 1 - t30
    drift = ("↑ judgment rising" if today_judg > j30 + 0.05 else
             "↓ slipping (more autopilot)" if today_judg < j30 - 0.05 else
             "→ holding the line")
    L = [f"  Atrophy · {date.isoformat()}",
         "  " + "─" * 48,
         "",
         f"  judgment today   {today_judg*100:>3.0f}%  {_bar(today_judg)}"]
    spk = (_spark(spark) + "   ") if spark else ""
    L.append(f"  trend  7d {j7*100:.0f}%  30d {j30*100:.0f}%  {spk}{drift}")
    L += ["", f"  active time      {_hms(total_active):<6} across {len(rows)} project(s)"]
    if envelope:
        first, last = envelope
        L.append(f"  mental window    {first:%H:%M} → {last:%H:%M}   "
                 f"({_hms((last - first).total_seconds())})")
    if supervision and supervision[0] > 0:
        run_sec, present_sec = supervision[0], supervision[1]
        passive_sec = supervision[2] if len(supervision) > 2 else 0
        mon = present_sec / run_sec
        line = (f"  monitoring       {mon*100:>3.0f}%  {_bar(mon)}   "
                f"{_hms(present_sec)} / {_hms(run_sec)} runtime")
        if passive_sec > 0:
            line += f" ; {_hms(passive_sec)} passive"
        L.append(line)
    val = value_summary(rows)
    if val["commits"] or val["business_pct"]:
        L.append(f"  value            {val['business_pct']:>3.0f}%  "
                 f"{_bar(val['business_pct'] / 100)}  business · {val['commits']} commits")
    truth = render_truth_line(rating, correlation)
    if truth:
        L.append("  " + truth)
    if review:   # review before accepting (2026 research finding)
        blind, eligible = review
        if eligible:
            L.append(f"  review           {eligible - blind} of {eligible} "
                     f"large outputs read · {blind} blind")
    if challenge:   # #2 active judgment (cognitive forcing practiced)
        c, total, ratio = challenge
        if total:
            L.append(f"  active judgment  {ratio*100:>3.0f}%  {_bar(ratio)}  "
                     f"{c}/{total} prompts challenge")
    if offloading:   # #1 volumetric delegation proxy (indicative)
        _, usr, ratio = offloading
        if usr:
            L.append(f"  delegation       {ratio:.1f}x agent output vs your typing")
    if llm_breakdown:   # axis 5b, topic-aware breakdown (on-demand lens)
        L.append("  " + llm_breakdown)
    L += ["",
          f"  {'projects':<17}{'judgment':<21}{'active':>6}  {'focus':>5}  {'commits':>4}",
          "  " + "─" * 48]
    # sorted by ascending judgment: the projects you steer the least come first (attention).
    for r in sorted(rows, key=lambda x: x["fordisme"], reverse=True):
        judg = 1 - r["fordisme"]
        k = r.get("kind", "perso")
        kind = "biz" if k == "business" else k[:5]
        L.append(f"  {r['project'][:9]:<9} {kind:<6}{judg*100:>3.0f}%  {_bar(judg, 17)} "
                 f"{_hms(r['active_sec']):>6}  {r['focus']*100:>4.0f}%  {r.get('commits', 0):>4}")
    return "\n".join(L)


def render_alert(msg):
    """Axis 2+3: a single alert, indicative framing (honest-mirror, not preachy).
    '' if nothing to report. The raw body comes from alert_message."""
    return f"Heads-up: {msg}" if msg else ""


def day_envelope(events):
    """(first_ts, last_ts) of the day = your 'mental window' (from when you
    sat down to the last, idle included). None if no event."""
    if not events:
        return None
    ts = [e["ts"] for e in events]
    return min(ts), max(ts)


def run_windows(events):
    """Intervals [prompt → end of the agent turn] = 'run in progress', per session.
    After the turn ends = the ball is in your court (reading), NOT a run."""
    by_sess = defaultdict(list)
    for e in events:
        by_sess[e.get("session", "")].append(e)
    windows = []
    for evs in by_sess.values():
        evs = sorted(evs, key=lambda e: e["ts"])
        j, n = 0, len(evs)
        while j < n:
            if evs[j]["role"] == "user":
                start = evs[j]["ts"]
                k, end = j + 1, None
                while k < n and evs[k]["role"] == "assistant":
                    end = evs[k]["ts"]
                    k += 1
                if end is not None:
                    windows.append((start, end))
                j = k
            else:
                j += 1
    return windows


def total_run_seconds(windows):
    return sum((e - s).total_seconds() for s, e in windows)


def read_presence(path):
    """Reads ~/.claude/presence.log written by presence-poll.sh.
    Lines 'epoch idle [focus]': focus 0/1 = terminal in the foreground (axis 2b), absent
    on old 2-field lines -> None. Returns (epoch, idle, focus) tuples."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                focus = int(parts[2]) if len(parts) >= 3 else None
                out.append((int(parts[0]), int(parts[1]), focus))
            except ValueError:
                continue
    return out


def _in_any_window(epoch, windows):
    t = datetime.fromtimestamp(epoch).astimezone()
    return any(s <= t <= e for s, e in windows)


def present_during_runs(presence, windows, idle_active_max=90, poll_interval=60):
    """Seconds where you were ACTIVELY present (input < idle_active_max s) WHILE
    a run was running = active monitoring ('switch panes to check').
    Tolerates 2- or 3-field tuples (back-compat with the old presence.log).
    # ponytail: idle_active_max=90 / poll=60 = calibration knobs."""
    if not presence or not windows:
        return 0.0
    secs = 0.0
    for rec in presence:
        epoch, idle = rec[0], rec[1]
        if idle >= idle_active_max:
            continue
        if _in_any_window(epoch, windows):
            secs += poll_interval
    return secs


def passive_during_runs(presence, windows, idle_active_max=90, poll_interval=60):
    """Axis 2b, motionless passive watching: seconds DURING a run where you touch
    nothing (idle >= idle_active_max) BUT the terminal is in the foreground (focus==1) =
    you stare at the screen without acting, distinct from "gone elsewhere" (focus 0).
    focus None (old format, undetermined) = not counted, caution."""
    if not presence or not windows:
        return 0.0
    secs = 0.0
    for rec in presence:
        if len(rec) < 3 or rec[2] != 1:   # need the explicit terminal focus
            continue
        epoch, idle = rec[0], rec[1]
        if idle < idle_active_max:         # low idle = active, that's active monitoring
            continue
        if _in_any_window(epoch, windows):
            secs += poll_interval
    return secs


_THRESHOLD_MIN_DEFAULT = 10
_TREND_DAYS = 30
# Local data outside the repo: ~/.atrophy/ (override via $ATROPHY_HOME). The source
# transcripts stay in ~/.claude/projects (written by Claude Code, universal).
_ATROPHY_HOME = os.environ.get("ATROPHY_HOME",
                               os.path.join(os.path.expanduser("~"), ".atrophy"))
_DEFAULT_LOG = os.path.join(_ATROPHY_HOME, "atrophy.md")
_DEFAULT_ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
_DEFAULT_PRESENCE = os.path.join(_ATROPHY_HOME, "presence.log")
_DEFAULT_RATINGS = os.path.join(_ATROPHY_HOME, "ratings.log")
_DEFAULT_PROJECTS = os.path.join(_ATROPHY_HOME, "projects.tsv")


def main(argv):
    ap = argparse.ArgumentParser(description="Atrophy: fordism & active time (v1).")
    ap.add_argument("--root", default=_DEFAULT_ROOT,
                    help="dir of Claude transcripts (default ~/.claude/projects)")
    ap.add_argument("--date", default=None, help="day to report (YYYY-MM-DD, default today local)")
    ap.add_argument("--log", default=_DEFAULT_LOG, help="markdown log path")
    ap.add_argument("--threshold-min", type=int, default=_THRESHOLD_MIN_DEFAULT,
                    help="idle gap threshold in minutes (default 10)")
    ap.add_argument("--no-log", action="store_true", help="report only, don't write the log")
    ap.add_argument("--presence", default=_DEFAULT_PRESENCE,
                    help="presence log from presence-poll.sh (default ~/.atrophy/presence.log)")
    ap.add_argument("--ratings", default=_DEFAULT_RATINGS,
                    help="self-ratings log 1-5 (default ~/.atrophy/ratings.log)")
    ap.add_argument("--rate", type=int, default=None, metavar="N",
                    help="record the day's 'judgment exercised' rating (1-5) then exit")
    ap.add_argument("--notify-line", action="store_true",
                    help="axis 2: print ONLY the alert (empty if no threshold crossed)")
    ap.add_argument("--projects", default=_DEFAULT_PROJECTS,
                    help="business/perso map 'project<TAB>kind' (default ~/.atrophy/projects.tsv)")
    ap.add_argument("--repo-base", default=None,
                    help="root to search for repos for commits/business (default $ATROPHY_REPO_BASE or ~/code)")
    ap.add_argument("--llm", action="store_true",
                    help="axis 5b: classify the day's substantive prompts (LOCAL offline LLM, "
                         "wakes the GPU at inference) into strategic/technical/creative")
    ap.add_argument("--llm-model", default=None,
                    help="gguf model path for --llm (default gemma-3-4b; Qwen-7B = more precise)")
    args = ap.parse_args(argv)

    day = (datetime.fromisoformat(args.date).date() if args.date
           else datetime.now().astimezone().date())

    if args.rate is not None:
        try:
            record_rating(args.ratings, day, args.rate)
        except ValueError as e:
            print(f"rating refused: {e}", file=sys.stderr)
            return 2
        print(f"noted {args.rate}/5 for {day.isoformat()}, thanks.")
        return 0
    start = day - timedelta(days=_TREND_DAYS - 1)
    threshold_sec = args.threshold_min * 60

    by_date = scan(args.root, start, day)
    today_events = by_date.get(day, [])
    day_vals = {d: day_fordisme(evs) for d, evs in by_date.items()}
    t7 = rolling(day_vals, day, 7)
    t30 = rolling(day_vals, day, 30)

    # Axis 2: silent notification, LIGHT path, short-circuited BEFORE the heavy work
    # (aggregate_day does git log + repo scans, useless here). today_ford of the day =
    # pooled day_fordisme = day_vals.get(day). Prints only the alert (empty if nothing).
    if args.notify_line:
        env = day_envelope(today_events)
        window_sec = (env[1] - env[0]).total_seconds() if env else 0.0
        # light: aggregate_day WITHOUT `day` -> no git/repo scan (cf. axis 4); just
        # the active time (sum per project) and the prompt count to gate the drift.
        light = aggregate_day(today_events, threshold_sec)
        active_sec = sum(r["active_sec"] for r in light)
        prompts = sum(r["prompts"] for r in light)
        msg = alert_message(day_vals.get(day, 0.0), t30, window_sec, active_sec, prompts)
        print(render_alert(msg), end="")
        return 0

    overrides = read_project_kinds(args.projects)
    rows = aggregate_day(today_events, threshold_sec, overrides=overrides, day=day,
                        repo_base=args.repo_base)

    ratings = read_ratings(args.ratings)
    judgement_by_day = {d: 1.0 - v for d, v in day_vals.items()}
    correlation = correlate_rating(ratings, judgement_by_day)

    llm_breakdown = None
    if args.llm:
        # Axis 5b: on-demand topic-aware lens. Lazy import (wakes the GPU
        # only here); classifies in memory, displays only counts (nothing persisted).
        import atrophy_llm
        labels = atrophy_llm.classify(substantive_prompts(today_events),
                                      model=args.llm_model)
        s = atrophy_llm.summarize(labels)
        if any(s.values()):
            llm_breakdown = (f"judgment exercised by topic (local LLM): "
                             f"{s['STRAT']} strategic · {s['TECH']} technical · "
                             f"{s['CREA']} creative · {s['AUTRE']} other")

    latencies = accept_latencies(today_events)
    review = blind_accepts(latencies)
    review_median = median_review_sec(latencies)
    challenge = challenge_ratio([e["text"] for e in today_events if e["role"] == "user"])
    offloading = offloading_ratio(today_events)

    envelope = day_envelope(today_events)
    windows = run_windows(today_events)
    presence = read_presence(args.presence)
    run_sec = total_run_seconds(windows)
    present_sec = present_during_runs(presence, windows)
    passive_sec = passive_during_runs(presence, windows)
    supervision = (run_sec, present_sec, passive_sec)

    tp = sum(r["prompts"] for r in rows)
    ta = sum(r["accept"] for r in rows)

    if not args.no_log and rows:
        fenetre = (f"{envelope[0]:%H:%M}→{envelope[1]:%H:%M} "
                   f"({_hms((envelope[1] - envelope[0]).total_seconds())})") if envelope else "-"
        val = value_summary(rows)
        log_day(args.log, day, {
            "fenetre": fenetre,
            "run": _hms(run_sec),
            "monitoring_pct": round(present_sec / run_sec * 100) if run_sec else 0,
            "fordisme_pct": round(ta / tp * 100) if tp else 0,
            "actif": _hms(sum(r["active_sec"] for r in rows)),
            "projets": len(rows),
            "commits": val["commits"],
            "business_pct": round(val["business_pct"]),
            "aveugle": review[0],
            "challenge_pct": round(challenge[2] * 100),
            "deleg_x": round(offloading[2], 1),   # ratio -> 1 decimal (not an int)
        })

    spark = [judgement_by_day.get(day - timedelta(days=k), 0.0) for k in range(6, -1, -1)]
    print(render_report(day, rows, t7, t30, envelope=envelope, supervision=supervision,
                        rating=ratings.get(day), correlation=correlation,
                        llm_breakdown=llm_breakdown, review=review,
                        review_median=review_median, challenge=challenge,
                        offloading=offloading, spark=spark))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
