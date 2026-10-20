#!/usr/bin/env python3
"""Diff-read and unchanged rates for the two pilot probes (STUDY_PLAN §8.1), beside the
pilot's own E_code runs of the same arms. No judging.

  compact_check probe: $EXPORTS/study-runs/probe-compact-check (E_code × compact_check,
    Haiku/Sonnet/Opus, runs 1–2) vs pilot E_code × compact and × none.
  effort probe: $EXPORTS/study-runs/probe-effort-{medium,low} (E_code × none/compact,
    Haiku/Sonnet, run 1) vs pilot E_code at high effort (run 1 and both runs).

Each rate is given over all 21 cases and over the 19 whose diff is within the study's
1,500-line rule. Prints Markdown and writes the numbers (no text) to
$POLISH_EVAL_DATA/Processed/polish-open-source-prose/probe-rates.json.

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/study/probe_rates.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

ROOTS = {"pilot (high)": pc.EXPORTS / "study-runs/pilot", "compact_check (high)": pc.EXPORTS / "study-runs/probe-compact-check",
         "medium": pc.EXPORTS / "study-runs/probe-effort-medium", "low": pc.EXPORTS / "study-runs/probe-effort-low"}
BIG = {"a2-airflow-71403", "a2-cpython-150425"}  # over 1,500 changed lines; excluded by the study's rule
SHORT = {"claude-haiku-5-5": "Haiku", "claude-sonnet-5-5": "Sonnet", "claude-opus-5-5": "Opus", "claude-fable-5-1": "Fable"}


def load(root: Path, cases: dict) -> list[dict]:
    rows = []
    for mp in sorted((root / "runs/claude").glob("*/E_code__*/run*/*/meta.json")):
        m = json.loads(mp.read_text())
        revised, _ = pc.split_output((mp.parent / "result.txt").read_text())
        text = revised if revised is not None else ""
        rows.append({"model": m["model"], "instruction": m["instruction"], "run": m["run"], "case": m["case"],
                     "effort": m["effort_used"], "read_diff": m["read_diff"], "parsed": revised is not None,
                     "unchanged": pc.normalized(cases[m["case"]]["input"]) == pc.normalized(text),
                     "cost": m.get("cost_usd") or 0.0, "seconds": m["seconds"]})
    return rows


def rate(rows: list[dict], key: str) -> str:
    return f"{sum(r[key] for r in rows) / len(rows):.2f}" if rows else "–"


def cell(rows: list[dict]) -> dict:
    small = [r for r in rows if r["case"] not in BIG]
    return {"n": len(rows), "read_diff": rate(rows, "read_diff"), "unchanged": rate(rows, "unchanged"),
            "n_19": len(small), "read_diff_19": rate(small, "read_diff"), "unchanged_19": rate(small, "unchanged"),
            "cost": round(sum(r["cost"] for r in rows), 2), "parsed": sum(r["parsed"] for r in rows)}


def table(title: str, groups: list[tuple[str, list[dict]]]) -> list[str]:
    out = [f"\n### {title}\n", "| model | arm | n | read diff | unchanged | read diff (19) | unchanged (19) | cost USD |",
           "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label, rows in groups:
        for model in [m for m in SHORT if any(r["model"] == m for r in rows)]:
            c = cell([r for r in rows if r["model"] == model])
            out.append(f"| {SHORT[model]} | {label} | {c['n']} | {c['read_diff']} | {c['unchanged']} | "
                       f"{c['read_diff_19']} | {c['unchanged_19']} | {c['cost']:.2f} |")
    return out


def main() -> None:
    cases = pc.read_cases()
    data = {k: load(v, cases) for k, v in ROOTS.items()}
    pilot = data["pilot (high)"]
    three = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
    two = ("claude-haiku-5-5", "claude-sonnet-5-5")
    sel = lambda rows, ins, models, runs=("1", "2"): [r for r in rows if r["instruction"] == ins and r["model"] in models
                                                    and r["run"] in runs]
    lines = ["## Probe rates (E_code; mechanical only, not judged)"]
    a = [("none (pilot)", sel(pilot, "none", three)), ("compact (pilot)", sel(pilot, "compact", three)),
         ("compact_check (probe)", sel(data["compact_check (high)"], "compact_check", three))]
    lines += table("(a) compact_check probe: two runs per case, effort high", a)
    b = []
    for ins in ("none", "compact"):
        b += [(f"{ins}, high (pilot run 1)", sel(pilot, ins, two, ("1",))),
              (f"{ins}, medium = default", sel(data["medium"], ins, two, ("1",))),
              (f"{ins}, low", sel(data["low"], ins, two, ("1",)))]
    lines += table("(b) effort probe: one run per case", b)
    print("\n".join(lines))
    summary = {"a": {lab: {SHORT[m]: cell([r for r in rows if r["model"] == m]) for m in three} for lab, rows in a},
               "b": {lab: {SHORT[m]: cell([r for r in rows if r["model"] == m]) for m in two} for lab, rows in b},
               "counts": {k: len(v) for k, v in data.items()}}
    (pc.PROC / "probe-rates.json").write_text(json.dumps(summary, indent=1) + "\n")


if __name__ == "__main__":
    main()
