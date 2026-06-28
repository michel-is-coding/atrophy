#!/usr/bin/env python3
"""Atrophy: LOCAL (offline) topic-aware LLM classification (axis 5b).

Lifts the acknowledged limit of text-only fordism: "delegation/engagement is really
significant only depending on the TOPIC (strategic vs technical)", a distinction
invisible from words alone. We classify the day's SUBSTANTIVE prompts (those that carry
a topic) into STRAT / TECH / CREA / AUTRE via llama.cpp and a local model (~/models/).

Frugality: ONE single batch call for N blocks (the cost = loading the model, which we
amortize). GPU woken only at inference, so NOT wired into the daily cron by
default; it is an on-demand lens (`atrophy.py --llm`).

HARD privacy: the text is read in memory and passed to the LOCAL binary only,
nothing leaves the machine (llama.cpp is offline by construction). We NEVER persist
the text: only aggregated LABELS/counts come out. Degrades gracefully
(all 'AUTRE') if the binary/model is missing: never breaks the report."""
import os
import re
import subprocess

_DEFAULT_BIN = "llama-cli"
_DEFAULT_MODEL = os.path.join(os.path.expanduser("~"), "models",
                             "gemma-3-4b-it-Q4_K_M.gguf")
_LABELS = ("STRAT", "TECH", "CREA", "AUTRE")
# A 'i: LABEL' answer line costs ~6 tokens; we bound -n wide (cap, not target:
# the model stops at EOS well before that on a normal day). ponytail: knobs.
_TOK_PER_LINE = 8
_TIMEOUT_S = 240
# Numbered answer line from the model: 'i: LABEL'. We anchor on it to IGNORE the
# banner / prompt re-echoed by the binary (which also contain STRAT/TECH/... in the
# instructions), --no-display-prompt does not strip them on this build.
_ANSWER_RE = re.compile(r"\d+\s*[:.\)]\s*(STRAT|TECH|CREA|AUTRE)")


def build_classify_prompt(blocks):
    """Builds the SINGLE batch prompt. Asks for one 'i: LABEL' line per block.
    Truncates each block (the topic fits in the first words; limits what is
    passed to the model)."""
    lines = [
        "Classify each request from a developer to their AI assistant into ONE label:",
        "STRAT = strategic/design/architecture topic (the judgment that counts most)",
        "TECH = technical/mechanical execution (grunt work delegable without risk)",
        "CREA = creative/writing/polish/naming",
        "AUTRE = neither one nor the other / ambiguous.",
        "Examples: 'rethink the cache architecture' -> STRAT ; "
        "'rename the variable x' -> TECH ; 'fix the indentation' -> TECH ; "
        "'find a catchy slogan' -> CREA.",
        "Reply ONLY with 'number: LABEL' lines, nothing else.",
        "",
    ]
    for i, b in enumerate(blocks, 1):
        snippet = " ".join((b or "").split())[:160]
        lines.append(f"{i}: {snippet}")
    lines.append("")
    lines.append("Answers:")
    return "\n".join(lines)


def _scan_label_tokens(up, n):
    """Fallback: scans the raw label tokens in order (non-numbered model)."""
    found, i = [], 0
    while i < len(up) and len(found) < n:
        best, pos = None, len(up)
        for lab in _LABELS:
            p = up.find(lab, i)
            if p != -1 and p < pos:
                best, pos = lab, p
        if best is None:
            break
        found.append(best)
        i = pos + len(best)
    return found


def parse_labels(text, n):
    """Extracts n labels. PRIORITY to numbered answer lines 'i: LABEL' (the requested
    format): this skips the re-echoed banner/prompt that also contain the label words.
    Falls back to a raw scan ONLY if no numbered line. Pads with 'AUTRE' if too few,
    truncates if too many. Case-insensitive."""
    up = (text or "").upper()
    found = [m.group(1) for m in _ANSWER_RE.finditer(up)]
    if not found:
        found = _scan_label_tokens(up, n)
    found += ["AUTRE"] * (n - len(found))
    return found[:n]


def run_llama(prompt, model=None, binary=None, timeout=None):
    """Runs the LOCAL binary and returns its output (generation only). Raises on
    failure/timeout (caught by classify)."""
    model = model or _DEFAULT_MODEL
    binary = binary or _DEFAULT_BIN
    # -st (single-turn) + --simple-io: one turn then exits (this build of llama-cli
    # dropped -no-cnv and otherwise loops interactively). NB: --no-display-prompt does
    # NOT strip the banner/prompt on this build -> parse_labels anchors on the
    # numbered lines to ignore them. -n bounded wide on the line count (cap, not
    # target). ponytail: flags = knob if the binary evolves.
    r = subprocess.run(
        [binary, "-m", model, "-ngl", "99", "--no-warmup", "-st", "--simple-io",
         "--no-display-prompt", "--temp", "0",
         "-n", str(max(16, _TOK_PER_LINE * (prompt.count(chr(10)) + 1))),
         "-p", prompt],
        capture_output=True, text=True, errors="replace",
        timeout=timeout or _TIMEOUT_S)
    if r.returncode != 0:
        raise RuntimeError(f"llama rc={r.returncode}: {r.stderr[-200:]}")
    return r.stdout


def classify(blocks, model=None, binary=None, timeout=None):
    """Returns one label per block. Degrades to ['AUTRE',...] if anything fails
    (binary absent, timeout, model missing), the report must never break."""
    blocks = [b for b in blocks if (b or "").strip()]
    if not blocks:
        return []
    try:
        out = run_llama(build_classify_prompt(blocks), model, binary, timeout)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError):
        # ValueError covers UnicodeDecodeError (non-UTF8 banner from the binary).
        return ["AUTRE"] * len(blocks)
    return parse_labels(out, len(blocks))


def summarize(labels):
    """Aggregated counts per category (stable keys, 0 by default), the only thing
    that comes out / can be displayed."""
    out = {lab: 0 for lab in _LABELS}
    for lab in labels:
        out[lab] = out.get(lab, 0) + 1
    return out
