#!/usr/bin/env python3
"""Score the 2026-10-04 model runs and write evals/results/runs-2026-10-04.json.

The raw runs live outside Git, under
$POLISH_EVAL_DATA/Exports/polish-open-source-prose/eval-runs-2026-10-04 (see
evals/README.md). This script reads only each run's final output, scores it against the
forward cases at commit 2a05713 with one literal rule for every model and condition, and
writes the outputs and scores, without local paths, session IDs, or event logs.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/score_runs.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data")) / "Exports/polish-open-source-prose/eval-runs-2026-10-04"
CASES_COMMIT = "2a05713"
CONDITIONS = ["no_skill", "one_sentence", "three_sentences", "v0.1.0", "v0.2.0"]
MODELS = {
    "claude-opus-5-5": {
        "claude_tags": True,
        "runs": {"no_skill": ["claude-next/runs/A/{id}", "claude-next/runs/A2/{id}"],
                 "one_sentence": ["claude-next/runs/Q/{id}", "claude-next/runs/Q2/{id}"],
                 "three_sentences": ["claude-next/runs/P/{id}", "claude-next/runs/P2/{id}"],
                 "v0.1.0": ["claude-next/runs/B/{id}", "claude-next/runs/B2/{id}"],
                 "v0.2.0": ["claude-next/runs/N3/{id}", "claude-next/runs/N4/{id}"]},
    },
    "gpt-6.1-sol": {
        "claude_tags": False,
        "runs": {"no_skill": ["codex-raw/runs/{id}/A"], "one_sentence": ["codex-c1-sol/runs/{id}/P"],
                 "three_sentences": ["codex-p-sol/runs/{id}/P"], "v0.1.0": ["codex-raw/runs/{id}/B"],
                 "v0.2.0": ["codex-next-sol/runs/{id}/B"]},
    },
    "gpt-6-astra": {
        "claude_tags": False,
        "runs": {"no_skill": ["astra/codex-raw/cases/{id}/A"], "one_sentence": ["codex-c1-astra/cases/{id}/A"],
                 "three_sentences": ["codex-p-astra/cases/{id}/A"], "v0.1.0": ["astra/codex-raw/cases/{id}/B"],
                 "v0.2.0": ["codex-next-astra/cases/{id}/B"]},
    },
}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).replace("\r\n", "\n").rstrip("\n")


def revised_text(raw: str, case: dict, claude_tags: bool) -> str:
    if claude_tags and case["mode"] != "provenance":
        m = re.search(r"<revised>\s*\n?(.*?)\n?\s*</revised>", raw, re.S)
        return m.group(1) if m else raw
    return raw


def passed(case: dict, text: str, claude_tags: bool) -> tuple[bool, bool]:
    t = nfc(text)
    unchanged = ("\n".join(l.rstrip() for l in t.strip().splitlines())
                 == "\n".join(l.rstrip() for l in nfc(case["input"]).strip().splitlines())) if claude_tags \
        else t == nfc(case["input"])
    ok = all(nfc(s) in t for s in case["must_preserve"]) and not any(nfc(s) in t for s in case["must_remove"])
    ok = ok and not any(nfc(s) in t and s not in case["input"] for s in case["must_not_introduce"])
    if case["mode"] == "keep":
        ok = ok and unchanged
    return ok, unchanged


def main() -> None:
    cases = json.loads(subprocess.check_output(
        ["git", "show", f"{CASES_COMMIT}:skills/polish-open-source-prose/tests/forward_cases.json"],
        cwd=REPO, text=True))["cases"]
    records, summary = [], {}
    for model, cfg in MODELS.items():
        summary[model] = {}
        for cond in CONDITIONS:
            per_run = []
            for k, pattern in enumerate(cfg["runs"][cond], 1):
                counts = Counter()
                for case in cases:
                    run = RUNS / pattern.format(id=case["id"])
                    out = run / ("result.txt" if cfg["claude_tags"] else "output.txt")
                    if not out.exists():
                        continue
                    text = revised_text(out.read_text(), case, cfg["claude_tags"])
                    ok, unchanged = passed(case, text, cfg["claude_tags"])
                    group = f"{case['locale']}/{case['mode']}"
                    counts[(group, "n")] += 1
                    counts[(group, "pass")] += ok
                    records.append({"model": model, "condition": cond, "run": k, "case": case["id"],
                                    "locale": case["locale"], "mode": case["mode"], "pass": ok,
                                    "unchanged": unchanged, "output": text})
                per_run.append({g: f"{counts[(g, 'pass')]}/{counts[(g, 'n')]}"
                                for g in sorted({g for g, _ in counts})})
            summary[model][cond] = per_run
    out = REPO / "evals/results/runs-2026-10-04.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"cases_commit": CASES_COMMIT, "summary": summary, "records": records},
                              ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
