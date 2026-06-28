#!/usr/bin/env python3
"""Plain-assert tests for atrophy.py, run: python3 tests/test_atrophy.py"""
import os, sys, traceback
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import atrophy


def test_parse_ts_returns_aware_datetime():
    dt = atrophy.parse_ts("2026-06-27T21:29:43.787Z")
    assert dt.tzinfo is not None, "must be timezone-aware"
    # 21:29 UTC is a fixed instant regardless of local tz
    assert dt.astimezone(timezone.utc).hour == 21
    assert dt.astimezone(timezone.utc).minute == 29


def test_project_of_takes_basename():
    assert atrophy.project_of("/home/dev/work/proj") == "proj"
    assert atrophy.project_of("/home/dev/work/crm/acme-crm") == "acme-crm"
    assert atrophy.project_of("") == "?"


def test_gap_split_merges_short_gaps_splits_long():
    base = datetime(2026, 6, 27, 10, 0, 0, tzinfo=timezone.utc)
    ts = [
        base,
        base + timedelta(minutes=2),   # +2min gap  -> active (<10)
        base + timedelta(minutes=4),   # +2min gap  -> active
        base + timedelta(minutes=30),  # +26min gap -> idle (>=10), not counted
        base + timedelta(minutes=31),  # +1min gap  -> active
    ]
    active = atrophy.gap_split(ts, threshold_sec=600)
    # counted gaps: 2 + 2 + 1 = 5 minutes = 300s ; the 26min gap is dropped
    assert active == 300, f"expected 300s active, got {active}"


def test_gap_split_handles_zero_or_one_event():
    assert atrophy.gap_split([], 600) == 0
    one = [datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc)]
    assert atrophy.gap_split(one, 600) == 0


def test_is_accept_prompt_flags_rubber_stamps():
    for t in ["ok", "OK", "oui", "vas-y", "vas y", "go", "continue",
              "parfait", "next", "ok go", "👍", "✅", "  yes  "]:
        assert atrophy.is_accept_prompt(t), f"should be accept: {t!r}"


def test_is_accept_prompt_rejects_substantive():
    for t in ["non, plutôt en Rust", "explique le gap-split",
              "ok mais change le seuil à 5 minutes et re-teste",
              "", "refais l'archi complètement"]:
        assert not atrophy.is_accept_prompt(t), f"should NOT be accept: {t!r}"


def test_is_accept_prompt_flags_english():
    # the tool must work for English-prompting users too (issue #5)
    for t in ["thanks", "perfect", "lgtm", "sounds good", "great", "sure", "go ahead",
              "do what you think is best", "up to you", "your call", "i trust you",
              "as you see fit", "we're done", "that's enough", "ship it", "good enough"]:
        assert atrophy.is_accept_prompt(t), f"english accept/delegate/closure: {t!r}"
    # real English instructions are engagement, not fordism:
    for t in ["implement the payment feature", "write the spec in detail",
              "refactor module X completely"]:
        assert not atrophy.is_accept_prompt(t), f"english instruction, not fordism: {t!r}"


def test_fordisme_ratio_counts_acceptances():
    texts = ["ok", "vas-y", "explique pourquoi tu fais ça", "go", ""]
    accept, total, ratio = atrophy.fordisme_ratio(texts)
    # "" is ignored ; 3 accepts ("ok","vas-y","go") of 4 substantive prompts
    assert (accept, total) == (3, 4)
    assert abs(ratio - 0.75) < 1e-9


def test_scan_reads_user_and_assistant_events_in_window(tmp_path_factory=None):
    import json, tempfile, pathlib
    from datetime import date
    with tempfile.TemporaryDirectory() as tmpdir:
        root = pathlib.Path(tmpdir)
        proj_dir = root / "-home-dev-work-proj"
        proj_dir.mkdir(parents=True)
        f = proj_dir / "sess1.jsonl"
        lines = [
            {"type": "user", "timestamp": "2026-06-27T10:00:00Z",
             "cwd": "/home/dev/work/proj",
             "message": {"role": "user", "content": "ok"}},
            {"type": "assistant", "timestamp": "2026-06-27T10:01:00Z",
             "cwd": "/home/dev/work/proj",
             "message": {"role": "assistant", "content": "done"}},
            {"type": "file-history-snapshot", "timestamp": "2026-06-27T10:02:00Z"},  # ignored
            {"type": "user", "timestamp": "2026-01-01T10:00:00Z",
             "cwd": "/home/dev/work/proj",
             "message": {"role": "user", "content": "old"}},  # out of window
        ]
        f.write_text("\n".join(json.dumps(x) for x in lines))

        by_date = atrophy.scan(root, date(2026, 6, 1), date(2026, 6, 30))
        assert date(2026, 6, 27) in by_date
        evs = by_date[date(2026, 6, 27)]
        assert len(evs) == 2, f"expected 2 in-window events, got {len(evs)}"
        assert {e["role"] for e in evs} == {"user", "assistant"}
        assert evs[0]["project"] == "proj"
        assert date(2026, 1, 1) not in by_date  # window filter works


def _ev(minute, project, role, text):
    return {"ts": datetime(2026, 6, 27, 10, minute, tzinfo=timezone.utc),
            "project": project, "role": role, "text": text}


def test_aggregate_day_per_project_rows():
    events = [
        _ev(0, "setup", "user", "ok"),
        _ev(2, "setup", "assistant", "done"),
        _ev(4, "setup", "user", "explique le design en détail"),
        _ev(0, "proj-a", "user", "vas-y"),
        _ev(1, "proj-a", "assistant", "ok"),
    ]
    rows = atrophy.aggregate_day(events, threshold_sec=600)
    by_proj = {r["project"]: r for r in rows}
    assert set(by_proj) == {"setup", "proj-a"}
    s = by_proj["setup"]
    assert s["active_sec"] == 240          # gaps 2min + 2min within threshold
    assert s["span_sec"] == 240            # 10:00 -> 10:04
    assert s["prompts"] == 2 and s["accept"] == 1   # "ok"=accept, "explique..."=no
    assert abs(s["fordisme"] - 0.5) < 1e-9
    assert abs(s["focus"] - 1.0) < 1e-9    # active == span here


def test_day_fordisme_is_overall_ratio():
    events = [
        _ev(0, "setup", "user", "ok"),
        _ev(1, "setup", "user", "go"),
        _ev(2, "proj-a", "user", "écris la spec en détaillant chaque cas"),
    ]
    # 2 accepts ("ok","go") of 3 substantive prompts across all projects
    assert abs(atrophy.day_fordisme(events) - (2 / 3)) < 1e-9


def test_rolling_means_over_last_n_days():
    from datetime import date
    day_vals = {
        date(2026, 6, 27): 0.4,
        date(2026, 6, 26): 0.2,
        date(2026, 6, 20): 1.0,   # within 30d, outside 7d
        date(2026, 5, 1): 0.0,    # outside 30d
    }
    end = date(2026, 6, 27)
    # last 7 days (06-21..06-27): 0.4 and 0.2 -> mean 0.3
    assert abs(atrophy.rolling(day_vals, end, 7) - 0.3) < 1e-9
    # last 30 days: 0.4, 0.2, 1.0 -> mean 0.5333...
    assert abs(atrophy.rolling(day_vals, end, 30) - (1.6 / 3)) < 1e-9


def test_rolling_empty_window_returns_zero():
    from datetime import date
    assert atrophy.rolling({}, date(2026, 6, 27), 7) == 0.0


def test_log_day_replaces_by_date():
    import tempfile, pathlib
    from datetime import date
    p = pathlib.Path(tempfile.mkdtemp()) / "atrophy.md"
    base = {"fenetre": "09:00→10:00 (1h)", "run": "30min",
            "monitoring_pct": 10, "fordisme_pct": 5, "actif": "45min", "projets": 3}
    atrophy.log_day(p, date(2026, 6, 27), base)
    atrophy.log_day(p, date(2026, 6, 27), dict(base, fordisme_pct=7))  # refresh same day
    body = p.read_text()
    assert body.count("| date |") == 1, "header once"
    assert body.count("| 2026-06-27 |") == 1, "one row, replaced not duplicated"
    assert "| 7 | 45min |" in body, "fordism refreshed"
    assert "| 5 | 45min |" not in body, "stale value gone"
    atrophy.log_day(p, date(2026, 6, 28), base)  # different day appends
    atrophy.log_day(p, date(2026, 6, 26), base)  # earlier day, inserted out of order
    out = p.read_text()
    assert out.count("| 2026-06-2") == 3
    # rows kept chronologically sorted regardless of write order
    i26, i27, i28 = (out.index("| 2026-06-26 |"), out.index("| 2026-06-27 |"),
                     out.index("| 2026-06-28 |"))
    assert i26 < i27 < i28, "rows must be date-sorted"


def test_render_report_frames_as_judgement_exercised():
    # Axis 3: capacity framing, not deficit. The headline celebrates JUDGMENT EXERCISED
    # (=1-fordism), not atrophy. fordism 64% -> judgment 36%.
    from datetime import date
    rows = [{"project": "proj-a", "active_sec": 3900, "span_sec": 5400,
             "focus": 0.72, "prompts": 14, "accept": 9, "fordisme": 0.64}]
    out = atrophy.render_report(date(2026, 6, 27), rows, t7=0.38, t30=0.31)
    assert "2026-06-27" in out
    assert "judgment today" in out.lower()         # positive framing
    assert "36%" in out                            # 100 - 64 = today's judgment
    assert "7d" in out and "30d" in out
    assert "proj-a" in out


def test_render_alert_capacity_framed():
    # indicative framing (prefix), not preachy; empty if no alert
    assert atrophy.render_alert(None) == ""
    out = atrophy.render_alert("judgment exercised dropped to 45% (30d baseline 70%)")
    assert "judgment exercised dropped" in out and "heads-up" in out.lower()


def test_is_accept_prompt_flags_delegation():
    for t in ["fais ce que tu penses être bon", "fais au mieux", "comme tu veux",
              "à toi de voir", "je te fais confiance", "comme tu le sens"]:
        assert atrophy.is_accept_prompt(t), f"delegation = fordism: {t!r}"


def test_is_accept_prompt_flags_closure():
    for t in ["c'est bon ça me suffit", "tout est bon ?", "on a fini ?",
              "c'est bon, ça me suffit, merci", "ça marche"]:
        assert atrophy.is_accept_prompt(t), f"closure = fordism: {t!r}"


def test_is_accept_prompt_flags_short_accept_directive():
    # Q2: accept-token + short instruction = full fordism.
    for t in ["vas-y inspecte", "oui passe à xhigh", "go continue", "continue"]:
        assert atrophy.is_accept_prompt(t), f"short-accept = fordism: {t!r}"
    # but a long, reasoned correction is NOT fordism:
    assert not atrophy.is_accept_prompt("ok mais change le seuil à 5 minutes et re-teste")


def test_synthetic_interrupt_markers_excluded():
    import json, tempfile, pathlib
    from datetime import date
    root = pathlib.Path(tempfile.mkdtemp())
    pd = root / "-home-dev-work-proj"; pd.mkdir(parents=True)
    (pd / "s.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"type": "user", "timestamp": "2026-06-27T10:00:00Z", "cwd": "/x/setup",
         "message": {"role": "user", "content": "[Request interrupted by user]"}},
        {"type": "user", "timestamp": "2026-06-27T10:01:00Z", "cwd": "/x/setup",
         "message": {"role": "user", "content": "real prompt"}},
    ]))
    by = atrophy.scan(root, date(2026, 6, 27), date(2026, 6, 27))
    texts = [e["text"] for e in by[date(2026, 6, 27)] if e["text"].strip()]
    assert texts == ["real prompt"], f"interrupt marker must be excluded, got {texts}"


def test_main_runs_on_fixture_and_writes_log():
    import json, tempfile, pathlib
    root = pathlib.Path(tempfile.mkdtemp())
    pd = root / "-home-dev-work-proj"; pd.mkdir(parents=True)
    # cwd outside ~/code -> basename 'atrophy-fixture' resolves no real repo
    # (hermetic: no git log on the dev's actual repo during the test).
    (pd / "s.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"type": "user", "timestamp": "2026-06-27T10:00:00Z",
         "cwd": "/x/atrophy-fixture", "message": {"role": "user", "content": "ok"}},
        {"type": "assistant", "timestamp": "2026-06-27T10:02:00Z",
         "cwd": "/x/atrophy-fixture", "message": {"role": "assistant", "content": "done"}},
    ]))
    logp = root / "atrophy.md"
    rc = atrophy.main(["--root", str(root), "--date", "2026-06-27", "--log", str(logp),
                       "--presence", str(root / "none.log")])
    assert rc == 0
    assert logp.exists()
    assert "| 2026-06-27 |" in logp.read_text()  # the day's summary written


def _sev(minute, role, session="s1"):
    return {"ts": datetime(2026, 6, 27, 10, minute, tzinfo=timezone.utc),
            "project": "setup", "role": role, "text": "", "session": session}


def test_day_envelope_first_last():
    evs = [_ev(5, "setup", "user", "a"), _ev(40, "setup", "assistant", "b"),
           _ev(20, "x", "user", "c")]
    first, last = atrophy.day_envelope(evs)
    assert first == datetime(2026, 6, 27, 10, 5, tzinfo=timezone.utc)
    assert last == datetime(2026, 6, 27, 10, 40, tzinfo=timezone.utc)
    assert atrophy.day_envelope([]) is None


def test_run_windows_prompt_to_turn_end():
    evs = [_sev(0, "user"), _sev(1, "assistant"), _sev(2, "assistant"),
           _sev(10, "user"), _sev(12, "assistant")]
    w = atrophy.run_windows(evs)
    assert w == [
        (datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc),
         datetime(2026, 6, 27, 10, 2, tzinfo=timezone.utc)),
        (datetime(2026, 6, 27, 10, 10, tzinfo=timezone.utc),
         datetime(2026, 6, 27, 10, 12, tzinfo=timezone.utc)),
    ]
    assert atrophy.total_run_seconds(w) == 240  # 2min + 2min


def test_present_during_runs_counts_active_in_window():
    w = [(datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc),
          datetime(2026, 6, 27, 10, 10, tzinfo=timezone.utc))]
    def ep(h, m):
        return int(datetime(2026, 6, 27, h, m, tzinfo=timezone.utc).timestamp())
    presence = [
        (ep(10, 2), 5),     # in the window, low idle (active) -> counts
        (ep(10, 5), 200),   # in the window but high idle (>90) -> no
        (ep(11, 0), 5),     # active but outside the window -> no
    ]
    secs = atrophy.present_during_runs(presence, w, idle_active_max=90, poll_interval=60)
    assert secs == 60


# ---------- Axis 1: ground truth (self-rating 1-5 + correlation) ----------

def test_record_and_read_rating_roundtrip():
    import tempfile, pathlib
    from datetime import date
    p = pathlib.Path(tempfile.mkdtemp()) / "ratings.log"
    atrophy.record_rating(p, date(2026, 6, 27), 4)
    assert atrophy.read_ratings(p) == {date(2026, 6, 27): 4}


def test_record_rating_replaces_same_day():
    import tempfile, pathlib
    from datetime import date
    p = pathlib.Path(tempfile.mkdtemp()) / "ratings.log"
    atrophy.record_rating(p, date(2026, 6, 27), 2)
    atrophy.record_rating(p, date(2026, 6, 27), 5)   # same day -> replaces
    atrophy.record_rating(p, date(2026, 6, 28), 3)
    assert atrophy.read_ratings(p) == {date(2026, 6, 27): 5, date(2026, 6, 28): 3}


def test_record_rating_rejects_out_of_range():
    import tempfile, pathlib
    from datetime import date
    p = pathlib.Path(tempfile.mkdtemp()) / "ratings.log"
    for bad in (0, 6, -1):
        try:
            atrophy.record_rating(p, date(2026, 6, 27), bad)
            assert False, f"{bad} must be rejected"
        except ValueError:
            pass


def test_read_ratings_skips_bad_calendar_date():
    import tempfile, pathlib
    from datetime import date
    p = pathlib.Path(tempfile.mkdtemp()) / "ratings.log"
    # valid form but impossible date (hand-edited) -> must NOT crash
    p.write_text("2026-13-40 3\n2026-06-27 4\n")
    assert atrophy.read_ratings(p) == {date(2026, 6, 27): 4}


def test_render_truth_line_undefined_when_zero_variance():
    # enough rated days but correlation undefined (same ratings) -> dedicated message,
    # not the misleading 'will populate (7/5)'
    line = atrophy.render_truth_line(4, (None, 7))
    assert "undefined" in line and "will populate" not in line


def test_pearson_perfect_and_degenerate():
    assert abs(atrophy.pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9   # perfect corr +
    assert abs(atrophy.pearson([1, 2, 3], [6, 4, 2]) + 1.0) < 1e-9   # perfect corr -
    assert atrophy.pearson([1, 1, 1], [1, 2, 3]) is None             # zero variance
    assert atrophy.pearson([1], [2]) is None                         # < 2 points


def test_correlate_rating_vs_judgement():
    from datetime import date
    ratings = {date(2026, 6, 25): 5, date(2026, 6, 26): 1, date(2026, 6, 27): 3}
    # judgment exercised = 1 - fordism; high felt <-> high metric -> positive r
    judgement = {date(2026, 6, 25): 0.9, date(2026, 6, 26): 0.2, date(2026, 6, 27): 0.5}
    r, n = atrophy.correlate_rating(ratings, judgement)
    assert n == 3
    assert r > 0.99


def test_correlate_rating_ignores_unmatched_days():
    from datetime import date
    ratings = {date(2026, 6, 25): 5, date(2026, 6, 26): 1}
    judgement = {date(2026, 6, 25): 0.9}  # only one common day
    r, n = atrophy.correlate_rating(ratings, judgement)
    assert n == 1 and r is None  # 1 point -> no correlation


# ---------- Axis 2: silent except for alerts ----------

def test_alert_message_silent_when_stable():
    # fordism low and close to the baseline -> no alert (silence)
    assert atrophy.alert_message(0.05, 0.07, window_sec=8 * 3600) is None
    # drift but below the 40% floor -> no alert (noise avoided)
    assert atrophy.alert_message(0.30, 0.05, window_sec=8 * 3600) is None


def test_alert_message_fires_on_fordisme_drift():
    # axis 3: the alert (only push) speaks CAPACITY like the rest, not 'fordism/deficit'
    msg = atrophy.alert_message(0.55, 0.30, window_sec=8 * 3600)
    assert msg is not None and "judgment" in msg.lower()
    assert "45%" in msg            # judgment = 1-0.55 = 45%
    assert "fordism" not in msg.lower()


def test_alert_message_fires_on_endless_day():
    msg = atrophy.alert_message(0.05, 0.07, window_sec=19 * 3600)
    assert msg is not None and "mental window" in msg.lower()


def test_alert_message_fires_on_too_much_active_time():
    # guard "too much used today": active time beyond the threshold
    msg = atrophy.alert_message(0.05, 0.07, window_sec=8 * 3600, active_sec=11 * 3600)
    assert msg is not None and "active time" in msg.lower()
    # below the threshold -> nothing
    assert atrophy.alert_message(0.05, 0.07, window_sec=8 * 3600, active_sec=6 * 3600) is None


def test_alert_message_fordisme_needs_enough_prompts():
    # intra-day: 3 prompts incl. 2 'ok' = 67% but sample too small -> no alert
    assert atrophy.alert_message(0.67, 0.10, prompts=3) is None
    # same ratio with enough prompts -> alert
    assert atrophy.alert_message(0.67, 0.10, prompts=20) is not None
    # prompts not provided (back-compat) -> no guard
    assert atrophy.alert_message(0.67, 0.10) is not None


def test_main_notify_line_silent_returns_empty(capfdless=None):
    import io, tempfile, pathlib
    from contextlib import redirect_stdout
    root = pathlib.Path(tempfile.mkdtemp())
    pd = root / "-home-dev-work-proj"; pd.mkdir(parents=True)
    import json
    (pd / "s.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"type": "user", "timestamp": "2026-06-27T10:00:00Z",
         "cwd": "/home/dev/work/proj", "message": {"role": "user", "content": "explain in detail the chosen design"}},
        {"type": "assistant", "timestamp": "2026-06-27T10:02:00Z",
         "cwd": "/home/dev/work/proj", "message": {"role": "assistant", "content": "ok"}},
    ]))
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = atrophy.main(["--root", str(root), "--date", "2026-06-27",
                           "--presence", str(root / "n.log"), "--notify-line"])
    assert rc == 0
    assert buf.getvalue().strip() == "", "stable day -> no notify line"


def test_main_rate_records_today():
    import tempfile, pathlib
    root = pathlib.Path(tempfile.mkdtemp())
    rp = root / "ratings.log"
    rc = atrophy.main(["--root", str(root), "--date", "2026-06-27",
                       "--ratings", str(rp), "--rate", "4"])
    assert rc == 0
    from datetime import date
    assert atrophy.read_ratings(rp) == {date(2026, 6, 27): 4}


def test_main_rate_rejects_bad_value():
    import tempfile, pathlib
    root = pathlib.Path(tempfile.mkdtemp())
    rc = atrophy.main(["--root", str(root), "--date", "2026-06-27",
                       "--ratings", str(root / "r.log"), "--rate", "9"])
    assert rc == 2, "rating out of range -> return code 2"


def test_render_truth_line_states():
    from datetime import date
    # enough days, strong correlation -> verdict 'matches your experience'
    line = atrophy.render_truth_line(4, (0.8, 6))
    assert "today's rating: 4/5" in line and "matches your experience" in line
    # decorrelated
    assert "needs review" in atrophy.render_truth_line(3, (-0.2, 6))
    # not enough days -> 'will populate' message
    assert "will populate" in atrophy.render_truth_line(3, (0.9, 2))
    # nothing at all
    assert atrophy.render_truth_line(None, (None, 0)) is None


# ---------- Axis 4: value / output (business vs perso + output proxies) ----------

def test_classify_project_heuristic_and_override():
    assert atrophy.classify_project("crm-acme") == "business"
    assert atrophy.classify_project("acme-crm") == "business"
    assert atrophy.classify_project("client-acme") == "business"
    assert atrophy.classify_project("setup") == "perso"
    assert atrophy.classify_project("dotfiles") == "perso"
    # override wins over the heuristic
    assert atrophy.classify_project("setup", {"setup": "business"}) == "business"
    assert atrophy.classify_project("crm-x", {"crm-x": "perso"}) == "perso"


def test_read_project_kinds_parses_tsv():
    import tempfile, pathlib
    p = pathlib.Path(tempfile.mkdtemp()) / "projects.tsv"
    p.write_text("setup\tperso\nacme-crm\tbusiness\n# comment\nbad line\n")
    kinds = atrophy.read_project_kinds(p)
    assert kinds == {"setup": "perso", "acme-crm": "business"}


def test_git_commits_on_counts_day(_=None):
    import tempfile, pathlib, subprocess
    repo = pathlib.Path(tempfile.mkdtemp())
    env = dict(os.environ, GIT_AUTHOR_DATE="2026-06-27T10:00:00",
               GIT_COMMITTER_DATE="2026-06-27T10:00:00",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a],
                                    capture_output=True, env=env)
    run("init", "-q")
    (repo / "f").write_text("x")
    run("add", "-A")
    run("commit", "-q", "-m", "c1")
    from datetime import date
    assert atrophy.git_commits_on(repo, date(2026, 6, 27)) == 1
    assert atrophy.git_commits_on(repo, date(2026, 6, 28)) == 0   # other day
    assert atrophy.git_commits_on(pathlib.Path(tempfile.mkdtemp()), date(2026, 6, 27)) == 0  # not a repo


def test_value_summary_business_share():
    rows = [
        {"project": "acme-crm", "kind": "business", "active_sec": 3600, "commits": 4},
        {"project": "setup", "kind": "perso", "active_sec": 1800, "commits": 2},
    ]
    v = atrophy.value_summary(rows)
    assert v["commits"] == 6
    assert abs(v["business_pct"] - (3600 / 5400 * 100)) < 1e-9  # 2/3 of active time


# ---------- Axis 5b: substantive prompts (input to the local LLM classifier) ----------

def test_substantive_prompts_keeps_long_user_only():
    evs = [
        _ev(0, "setup", "user", "ok"),                                   # short -> no
        _ev(1, "setup", "assistant", "here is a very long detailed answer " * 5),  # assistant -> no
        _ev(2, "setup", "user", "redo the entire architecture of the payment module, rethinking all the data flows"),
        _ev(3, "setup", "user", ""),                                     # empty -> no
    ]
    out = atrophy.substantive_prompts(evs)
    assert out == ["redo the entire architecture of the payment module, rethinking all the data flows"]


# ---------- Axis 5a: terminal focus (motionless passive watching vs gone) ----------

def test_read_presence_parses_optional_focus():
    import tempfile, pathlib
    p = pathlib.Path(tempfile.mkdtemp()) / "presence.log"
    p.write_text("1782646024 0\n1782646084 4 1\n1782646144 200 0\njunk\n")
    recs = atrophy.read_presence(p)
    # old 2-field line -> focus None; new 3-field -> 0/1; bad line ignored
    assert recs == [(1782646024, 0, None), (1782646084, 4, 1), (1782646144, 200, 0)]


def test_present_during_runs_back_compat_two_field():
    from datetime import datetime, timezone
    w = [(datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc),
          datetime(2026, 6, 27, 10, 10, tzinfo=timezone.utc))]
    ep = int(datetime(2026, 6, 27, 10, 2, tzinfo=timezone.utc).timestamp())
    # 2-field tuples (old presence format) must still work
    assert atrophy.present_during_runs([(ep, 5)], w) == 60


def test_passive_during_runs_focused_idle_only():
    from datetime import datetime, timezone
    w = [(datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc),
          datetime(2026, 6, 27, 10, 10, tzinfo=timezone.utc))]
    def ep(m):
        return int(datetime(2026, 6, 27, 10, m, tzinfo=timezone.utc).timestamp())
    presence = [
        (ep(2), 200, 1),   # high idle + terminal foreground -> passive watching ✓
        (ep(4), 200, 0),   # high idle but gone elsewhere (focus 0) -> no
        (ep(6), 5, 1),     # active (low idle) -> that's active monitoring, not passive
        (ep(8), 200, None),# focus unknown (old format) -> not counted (cautious)
    ]
    secs = atrophy.passive_during_runs(presence, w, idle_active_max=90, poll_interval=60)
    assert secs == 60


# ---------- 2026 research: review before accepting (over-reliance) ----------

def _tev(sec, role, text, session="s1"):
    return {"ts": datetime(2026, 6, 27, 10, 0, sec, tzinfo=timezone.utc),
            "role": role, "text": text, "session": session, "project": "p"}


def test_accept_latencies_pairs_accept_with_preceding_turn():
    evs = [
        _tev(0, "user", "fais le refactor du module paiement stp"),
        _tev(1, "assistant", "x" * 600),         # big output...
        _tev(3, "assistant", "y" * 200),         # ...same turn (ends at +3s)
        _tev(8, "user", "ok"),                   # accepted 5s after the turn ends
        _tev(20, "assistant", "z" * 50),
        _tev(40, "user", "non, plutôt en deux étapes détaillées et re-teste"),  # not accept
    ]
    lat = atrophy.accept_latencies(evs)
    assert lat == [(5.0, 800)], f"got {lat}"   # 1 acceptance: 5s, output 800 chars


def test_accept_latencies_ignores_first_prompt_without_turn():
    evs = [_tev(0, "user", "ok"), _tev(2, "assistant", "a" * 100)]
    assert atrophy.accept_latencies(evs) == []   # initial 'ok' = no preceding turn


def test_blind_accepts_flags_fast_accept_on_big_output():
    lat = [
        (4.0, 900),     # big output accepted in 4s -> blind
        (120.0, 900),   # big output but 2min of review -> read, OK
        (3.0, 200),     # fast but small output -> not significant
    ]
    blind, eligible = atrophy.blind_accepts(lat, min_len=500, max_latency=15)
    assert (blind, eligible) == (1, 2)   # 2 eligible (>=500), 1 blind


# ---------- Research findings #1 #2 #3 ----------

def test_offloading_ratio_chars_produced_per_input():
    evs = [
        _tev(0, "user", "abc"),            # 3 chars input
        _tev(1, "assistant", "x" * 100),
        _tev(2, "user", "de"),             # 2 chars input
        _tev(3, "assistant", "y" * 50),
    ]
    asst, usr, ratio = atrophy.offloading_ratio(evs)
    assert (asst, usr) == (150, 5)
    assert abs(ratio - 30.0) < 1e-9        # the agent produced 30x your typed input
    # zero input -> ratio 0 (no division by zero)
    assert atrophy.offloading_ratio([_tev(0, "assistant", "zzz")])[2] == 0.0


def test_is_challenge_flags_doubt_and_correction():
    for t in ["es-tu sûr ?", "vérifie le calcul stp", "non plutôt en deux étapes",
              "re-teste", "prouve-le", "et si ça déborde ?", "montre-moi le diff",
              "je ne suis pas d'accord"]:
        assert atrophy.is_challenge(t), f"challenge expected: {t!r}"
    # negatives, incl. false positives fixed at review (precision > recall):
    for t in ["ok", "vas-y", "merci", "fais le refactor du module", "",
              "j'approuve ton plan",          # 'prouve' bounded -> no more match
              "fais plutôt un refactor",       # bare 'plutôt' removed
              "je t'explique le contexte",     # 'explique' removed (narrative)
              "c'est pourquoi il faut un guard",  # 'pourquoi' removed
              "le chemin critique du build"]:  # 'critique' removed
        assert not atrophy.is_challenge(t), f"NOT a challenge: {t!r}"


def test_is_challenge_flags_english():
    for t in ["are you sure?", "verify the calculation", "prove it",
              "what if it overflows?", "i disagree with this",
              "reconsider this approach", "show me the diff", "what about the risks?"]:
        assert atrophy.is_challenge(t), f"english challenge: {t!r}"
    # English non-challenges (avoid the why/explain narrative false positives):
    for t in ["explain the design", "let me explain the context", "implement it", "ok"]:
        assert not atrophy.is_challenge(t), f"english non-challenge: {t!r}"


def test_challenge_ratio_counts_active_judgement():
    texts = ["ok", "es-tu sûr ?", "vérifie", "fais X", ""]
    c, total, ratio = atrophy.challenge_ratio(texts)
    assert (c, total) == (2, 4)            # empty ignored; 2 challenges of 4
    assert abs(ratio - 0.5) < 1e-9


def test_median_review_sec_of_eligible():
    lat = [(4.0, 900), (120.0, 900), (3.0, 200)]   # 2 eligible (>=500): 4 and 120
    assert atrophy.median_review_sec(lat, min_len=500) == 62.0
    assert atrophy.median_review_sec([], min_len=500) is None


def test_defaults_live_under_atrophy_home():
    import os
    home = os.path.expanduser("~")
    assert atrophy._DEFAULT_LOG == os.path.join(home, ".atrophy", "atrophy.md")
    assert atrophy._DEFAULT_RATINGS == os.path.join(home, ".atrophy", "ratings.log")
    assert atrophy._DEFAULT_PRESENCE == os.path.join(home, ".atrophy", "presence.log")
    assert atrophy._DEFAULT_PROJECTS == os.path.join(home, ".atrophy", "projects.tsv")
    assert atrophy._DEFAULT_ROOT == os.path.join(home, ".claude", "projects")


def _run():
    tests = sorted((k, v) for k, v in globals().items()
                   if k.startswith("test_") and callable(v))
    fails = 0
    for name, fn in tests:
        try:
            fn(); print(f"PASS {name}")
        except Exception as e:
            fails += 1
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests)-fails}/{len(tests)} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    _run()
