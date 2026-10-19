#!/usr/bin/env python3
"""Check that every round-3 run received exactly the prompt PLAN.md specifies.

For each saved round-3 prompt of a prefix condition (compact_problems, skill_inline, and the
three_sentences rerun), the text must end with the round-2 no_skill prompt for the same set,
configuration, run, and case, and what precedes it must be the condition's prefix file
(surrounding whitespace ignored); its run directory must not contain the skill. A v0.2.0
rerun prompt must equal the round-2 v0.2.0 prompt for the same path. A wrong prefix, a
changed task prompt, or a skill in a prefix run all fail this check. Run it after the
runs and before scoring.

The runners save each prompt next to the output; pass its file name if it is not
prompt.txt.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/round3/check_prompts.py [--prompt-name prompt.txt]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNS = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data")) / "Exports/polish-open-source-prose/eval-runs-2026-10-04"
PREFIX = {"compact_problems": REPO / "evals/prompts/compact-problems.txt",
          "skill_inline": REPO / "evals/prompts/skill-inline-v0.2.0.txt",
          "three_sentences": REPO / "evals/prompts/three-sentences.txt"}
SAME_AS_ROUND2 = ["v0.2.0"]
SKILL_MARKERS = (".claude/skills", ".agents/skills", "AGENTS.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-name", default="prompt.txt")
    o = ap.parse_args()
    checked, bad = 0, []
    for cond, prefix_file in PREFIX.items():
        prefix = prefix_file.read_text().strip()
        for new in sorted((RUNS / "round3").glob(f"runs-a*/*/*/{cond}/**/{o.prompt_name}")):
            rel = new.relative_to(RUNS / "round3")
            old = RUNS / "round2" / Path(*[("no_skill" if p == cond else p) for p in rel.parts])
            if not old.exists():
                bad.append(f"{rel}: no round-2 no_skill prompt at {old.relative_to(RUNS)}")
                continue
            got, base = new.read_text(), old.read_text()
            if not got.endswith(base.strip()) and not got.endswith(base):
                bad.append(f"{rel}: task prompt differs from round-2 no_skill")
            else:
                head = got[: got.rfind(base.strip())].strip()
                if head != prefix:
                    bad.append(f"{rel}: prefix is not {prefix_file.name}")
            for marker in SKILL_MARKERS:
                if (new.parent / marker).exists():
                    bad.append(f"{rel}: {marker} present in the run directory")
            checked += 1
    for cond in SAME_AS_ROUND2:
        for new in sorted((RUNS / "round3").glob(f"runs-a*/*/*/{cond}/**/{o.prompt_name}")):
            rel = new.relative_to(RUNS / "round3")
            old = RUNS / "round2" / rel
            if not old.exists():
                bad.append(f"{rel}: no round-2 prompt at {old.relative_to(RUNS)}")
            elif new.read_text() != old.read_text():
                bad.append(f"{rel}: differs from the round-2 {cond} prompt")
            checked += 1
    print(f"{checked} round-3 prompts checked; {len(bad)} problems")
    for b in bad[:30]:
        print("  ", b)
    if bad or not checked:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
