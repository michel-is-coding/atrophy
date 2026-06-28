#!/usr/bin/env python3
"""Plain-assert tests for atrophy_llm.py, run: python3 tests/test_atrophy_llm.py
Does NOT need the real model: a deterministic fake binary simulates llama-cli."""
import os, sys, stat, tempfile, pathlib, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import atrophy_llm as L


def _fake_bin(output):
    """Creates a fake 'llama-cli' that prints `output` whatever the args."""
    d = pathlib.Path(tempfile.mkdtemp())
    p = d / "fake-llama"
    p.write_text("#!/usr/bin/env bash\ncat <<'EOF'\n" + output + "\nEOF\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(p)


def test_build_prompt_lists_blocks_and_labels():
    pr = L.build_classify_prompt(["redo the payment architecture", "rename the variable"])
    assert "1: redo the payment architecture" in pr
    assert "2: rename the variable" in pr
    assert "STRAT" in pr and "TECH" in pr and "CREA" in pr


def test_build_prompt_truncates_long_block():
    long = "x" * 500
    pr = L.build_classify_prompt([long])
    assert "x" * 160 in pr and "x" * 200 not in pr   # truncated to 160


def test_parse_labels_in_order():
    out = "1: STRAT\n2: TECH\n3: CREA\n4: AUTRE"
    assert L.parse_labels(out, 4) == ["STRAT", "TECH", "CREA", "AUTRE"]


def test_parse_labels_case_insensitive_numbered():
    out = "answers:\n1: Strat\n2: tech done"
    assert L.parse_labels(out, 2) == ["STRAT", "TECH"]


def test_parse_labels_ignores_echoed_banner():
    # real bug: this build re-echoes the prompt (instructions contain STRAT/TECH/CREA/
    # AUTRE + examples). We anchor on 'i: LABEL' -> we ignore the banner.
    out = ("STRAT = strategic\nTECH = technical\nCREA = creative\nAUTRE = other\n"
           "Examples: 'x' -> STRAT ; 'y' -> TECH ; 'z' -> CREA.\n"
           "Answers:\n1: TECH\n2: CREA")
    assert L.parse_labels(out, 2) == ["TECH", "CREA"]


def test_parse_labels_pads_when_too_few():
    assert L.parse_labels("STRAT", 3) == ["STRAT", "AUTRE", "AUTRE"]


def test_parse_labels_truncates_when_too_many():
    assert L.parse_labels("STRAT TECH CREA AUTRE", 2) == ["STRAT", "TECH"]


def test_classify_with_fake_binary():
    fake = _fake_bin("1: STRAT\n2: TECH\n3: CREA")
    labels = L.classify(["a", "b", "c"], model="/dev/null", binary=fake, timeout=10)
    assert labels == ["STRAT", "TECH", "CREA"]


def test_classify_ignores_empty_blocks():
    fake = _fake_bin("1: STRAT")
    assert L.classify(["", "  ", None], binary=fake) == []   # nothing to classify


def test_classify_degrades_when_binary_missing():
    labels = L.classify(["a", "b"], binary="/no/such/llama-cli-xyz")
    assert labels == ["AUTRE", "AUTRE"]   # never breaks the report


def test_classify_degrades_on_nonzero_exit():
    d = pathlib.Path(tempfile.mkdtemp())
    p = d / "boom"
    p.write_text("#!/usr/bin/env bash\nexit 3\n")
    p.chmod(0o755)
    assert L.classify(["a"], binary=str(p)) == ["AUTRE"]


def test_summarize_counts():
    s = L.summarize(["STRAT", "STRAT", "TECH"])
    assert s["STRAT"] == 2 and s["TECH"] == 1 and s["CREA"] == 0 and s["AUTRE"] == 0


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
