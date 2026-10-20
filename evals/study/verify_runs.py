#!/usr/bin/env python3
"""Verify pilot runs (PILOT_DESIGN §3): every run finished and parsed, used the pinned build,
loaded the skill only in the skill condition, and saw only the evidence its arm allows.
A run is never failed for leaving diff.patch unread.

Usage: verify_runs.py [--list-bad] [--expect N] [--quiet]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

CLAUDE_MARKERS = (".claude/skills", "polish-open-source-prose-v0")
EVIDENCE_WORDS = {"E_code": "The diff of this change is in the file diff.patch",
                  "E1": "A reviewer left this comment on the pull request:"}


def check(d: Path, bad: list[str]) -> dict:
    m = json.loads((d / "meta.json").read_text())
    s = (d / "stream.jsonl").read_text() if (d / "stream.jsonl").exists() else ""
    prompt = (d / "prompt.txt").read_text()
    listing = (d / "work-listing.txt").read_text() if (d / "work-listing.txt").exists() else ""
    evidence, instruction = m["evidence"], m["instruction"]
    skill_uses = 0
    for line in s.splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "assistant":
            skill_uses += sum(1 for b in e["message"]["content"] if b["type"] == "tool_use" and b["name"] == "Skill")
    if m.get("effort_requested", "high") != pc.EFFORT or m.get("effort_used") != pc.EFFORT:
        bad.append(f"{d}: effort {m.get('effort_requested')}/{m.get('effort_used')}, expected {pc.EFFORT}")
    if m["rc"] != 0:
        bad.append(f"{d}: rc={m['rc']}")
    if not (d / "result.txt").read_text().strip():
        bad.append(f"{d}: empty result.txt")
    if not m.get("parsed"):
        bad.append(f"{d}: no <revised> block")
    if m.get("claude_code_version") != pc.CLAUDE_VERSION:
        bad.append(f"{d}: claude_code_version={m.get('claude_code_version')}")
    if instruction == "skill":
        if not m["polish_skills_listed"]:
            bad.append(f"{d}: skill arm but no skills listed")
        if "polish-open-source-prose-v020" not in s:
            bad.append(f"{d}: skill arm but stream never mentions the v020 skill")
        if not prompt.startswith(pc.SLASH):
            bad.append(f"{d}: skill arm without slash command")
    else:
        if m["polish_skills_listed"] or skill_uses or any(k in s for k in CLAUDE_MARKERS):
            bad.append(f"{d}: SKILL LOADED in {instruction} arm")
        compact = prompt.startswith(pc.COMPACT + "\n\n")
        check_ = prompt.startswith(pc.COMPACT_CHECK + "\n\n")
        if (instruction == "compact") != compact or (instruction == "compact_check") != check_:
            bad.append(f"{d}: compact prefix mismatch")
    for ev, words in EVIDENCE_WORDS.items():
        if (evidence == ev) != (words in prompt):
            bad.append(f"{d}: evidence paragraph mismatch for {evidence}")
    if evidence == "E0":
        if any(name in listing for name in ("diff.patch", "ci.md", "review.md")) or m["read_diff"] or m["read_review"] or m["read_ci"]:
            bad.append(f"{d}: E0 run had evidence files")
    if evidence == "E_code":
        # The description itself may contain the word "reviewer"; check for the review text.
        if "review.md" in listing or m["read_review"] or pc.review_body(m["case"]) in prompt:
            bad.append(f"{d}: E_code run saw the review")
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-bad", action="store_true")
    ap.add_argument("--expect", type=int)
    ap.add_argument("--quiet", action="store_true")
    o = ap.parse_args()
    bad, rows = [], []
    for d in sorted(p for p in (pc.PILOT / "runs/claude").glob("*/*/run*/*") if p.is_dir()):
        if not (d / "meta.json").exists():
            bad.append(f"{d}: INCOMPLETE (no meta.json)")
            continue
        m = check(d, bad)
        rows.append((m["model"], m["evidence"], m["instruction"], m["run"], m["case"], m["rc"], m["seconds"],
                     m.get("cost_usd"), m["read_diff"]))
    bad_dirs = sorted({b.split(": ", 1)[0] for b in bad})
    if o.list_bad:
        print("\n".join(bad_dirs))
        raise SystemExit(1 if bad_dirs else 0)
    print(f"{len(rows)} runs checked; {len(bad)} problems in {len(bad_dirs)} run directories")
    if not o.quiet:
        for r in rows:
            print("  ", *r)
    for b in bad:
        print("PROBLEM", b)
    if o.expect is not None and len(rows) - len(bad_dirs) != o.expect:
        print(f"EXPECTED {o.expect} good runs, have {len(rows) - len(bad_dirs)}")
        raise SystemExit(1)
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
