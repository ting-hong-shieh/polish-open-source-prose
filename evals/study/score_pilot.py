#!/usr/bin/env python3
"""Score the pilot runs mechanically and collect one record per output.

Reads $PILOT_ROOT/runs/claude/**/meta.json and result.txt; writes
$POLISH_EVAL_DATA/Processed/polish-open-source-prose/pilot-records.json (holds third-party
text; stays outside Git) with, per output: model, evidence, instruction, run, case, the
revised text and note, unchanged (normalized equality), edit_ratio (character Levenshtein
distance over input length), the diff/review/ci read flags, cost, usage, and seconds, plus
the attempt number and flags: runs listed in pilot-reruns.json (kept from attempt 5 after a
verifier false positive) carry attempt 5 and the flag "rerun_verifier_false_positive".
Content never removes a run (STUDY_PLAN, Rerun rule); it only adds flags.

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/study/score_pilot.py [--out PATH]
--out writes the records elsewhere (for a dry run that must not touch the official file).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rapidfuzz.distance import Levenshtein

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=pc.PROC / "pilot-records.json",
                    help="where to write the records (default: the official pilot-records.json)")
    o = ap.parse_args()
    cases = pc.read_cases()
    reruns = json.loads((Path(__file__).resolve().parent / "pilot-reruns.json").read_text())
    rerun_keys = {(r["model"], r["evidence"], r["instruction"], r["run"], r["case"]) for r in reruns["runs"]}
    records = []
    for meta_path in sorted((pc.PILOT / "runs/claude").glob("*/*/run*/*/meta.json")):
        m = json.loads(meta_path.read_text())
        raw = (meta_path.parent / "result.txt").read_text()
        revised, note = pc.split_output(raw)
        case = cases[m["case"]]
        text = revised if revised is not None else raw
        a, b = pc.normalized(case["input"]), pc.normalized(text)
        records.append({**{k: m[k] for k in ("model", "evidence", "instruction", "run", "case", "rc", "seconds",
                                               "cost_usd", "usage", "effort_used", "read_diff", "read_review", "read_ci")},
                        "parsed": revised is not None, "output": text, "note": note,
                        "unchanged": a == b, "edit_ratio": round(Levenshtein.distance(a, b) / max(1, len(a)), 4)})
        key = (m["model"], m["evidence"], m["instruction"], m["run"], m["case"])
        rerun = pc.PILOT == pc.EXPORTS / "study-runs/pilot" and key in rerun_keys
        records[-1].update({"attempt": reruns["attempt"] if rerun else 1,
                            "flags": ["rerun_verifier_false_positive"] if rerun else []})
    out = o.out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps({"pilot_root": str(pc.PILOT), "records": records}, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, out)
    by_arm: dict[str, list] = {}
    for r in records:
        by_arm.setdefault(pc.arm(r["evidence"], r["instruction"]), []).append(r)
    print(f"{len(records)} records -> {out}")
    for k, rs in sorted(by_arm.items()):
        print(f"  {k:<18} n={len(rs):<4} unchanged={sum(r['unchanged'] for r in rs) / len(rs):.2f} "
              f"read_diff={sum(r['read_diff'] for r in rs) / len(rs):.2f} parsed={sum(r['parsed'] for r in rs)}")


if __name__ == "__main__":
    main()
