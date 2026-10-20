#!/usr/bin/env python3
"""Analyze the pilot (PILOT_PLAN primary and secondary, with STUDY_PLAN §5 outcomes).

Reads pilot-records.json and pilot-judgments.json; writes evals/results/pilot-analysis.json
(aggregates only). Outcomes per output: complete clean fix (addressed 1, code-consistent,
not invented, not damaged), mean clean-fix (addressed × (1−invented) × (1−damaged)), and
each label. Aggregation: runs averaged within a configuration, four configurations equal
weight, judges averaged (and reported separately).

Primary: E1 − E0 on complete clean fix, pooled over the three instructions; paired
case-bootstrap 95% interval (5,000 resamples, seed 20261020) and exact sign test.
Secondary family (Holm): E_code − E0 (clean), E1 − E_code (clean), E1 − E0 (damaged),
skill − none under E1 (clean).

Smoke test: --smoke-round3 recomputes the round-3 A2 clean-fix means from the round-3
labels through this script's aggregation and compares with round3-analysis.json.

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/study/analyze_pilot.py [--smoke-round3]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

SEED, RESAMPLES = 20261020, 5000
RESULTS = pc.REPO / "evals/results"


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, ps[i] * (len(ps) - rank))
        adj[i] = min(1.0, running)
    return adj


def case_means(rows: list[dict], value) -> dict[str, float]:
    """{case: mean over configurations of (mean over runs and judges)}."""
    cells: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        v = value(r)
        if v is not None:
            cells[r["case"]][r["model"]].append(float(v))
    return {c: float(np.mean([np.mean(v) for v in ms.values()])) for c, ms in cells.items()}


def contrast(a: dict[str, float], b: dict[str, float], rng: np.random.Generator) -> dict:
    cases = sorted(set(a) & set(b))
    d = np.array([a[c] - b[c] for c in cases])
    wins, losses = int((d > 1e-9).sum()), int((d < -1e-9).sum())
    boots = d[rng.integers(0, len(d), size=(RESAMPLES, len(d)))].mean(1)
    return {"cases": len(cases), "mean_a": round(float(np.mean([a[c] for c in cases])), 3),
            "mean_b": round(float(np.mean([b[c] for c in cases])), 3), "diff": round(float(d.mean()), 3),
            "wins": wins, "losses": losses, "p": sign_test(wins, losses),
            "ci95": [round(float(x), 3) for x in np.percentile(boots, [2.5, 97.5])]}


def outcomes(j: dict) -> dict:
    a = float(j["addressed"])
    inv, dmg, cc = bool(j["invented"]), bool(j["damaged"]), bool(j.get("code_consistent", True))
    return {"complete": float(a == 1 and cc and not inv and not dmg), "clean": a * (1 - inv) * (1 - dmg),
            "addressed": a, "invented": float(inv), "damaged": float(dmg), "code_consistent": float(cc),
            "asked_unanswerable": float(j.get("asked") == "unanswerable"), "asked_any": float(j.get("asked", "none") != "none")}


def join(records: list[dict], judgments: dict) -> list[dict]:
    """One row per (output, judge) with the outcome values."""
    labels: dict = {}
    for key, rows in judgments.items():
        judge = key.split(":", 1)[0]
        for r in rows:
            labels[(judge, r["model"], r["evidence"], r["instruction"], str(r["run"]), r["case"])] = r
    out = []
    for rec in records:
        for judge in sorted({k[0] for k in labels}):
            j = labels.get((judge, rec["model"], rec["evidence"], rec["instruction"], str(rec["run"]), rec["case"]))
            if j:
                out.append({**rec, "judge": judge, **outcomes(j)})
    return out


def analyze(rows: list[dict]) -> dict:
    rng = np.random.default_rng(SEED)
    sel = lambda ev=None, ins=None: [r for r in rows if (ev is None or r["evidence"] == ev) and (ins is None or r["instruction"] == ins)]  # noqa: E731
    cm = lambda rs, f: case_means(rs, lambda r: r[f])  # noqa: E731
    primary = contrast(cm(sel("E1"), "complete"), cm(sel("E0"), "complete"), rng)
    primary["contrast"] = "E1 - E0: complete clean fix"
    secondary = [
        ("E_code - E0: complete clean fix", contrast(cm(sel("E_code"), "complete"), cm(sel("E0"), "complete"), rng)),
        ("E1 - E_code: complete clean fix", contrast(cm(sel("E1"), "complete"), cm(sel("E_code"), "complete"), rng)),
        ("E1 - E0: damaged", contrast(cm(sel("E1"), "damaged"), cm(sel("E0"), "damaged"), rng)),
        ("E1: skill - none: complete clean fix", contrast(cm(sel("E1", "skill"), "complete"), cm(sel("E1", "none"), "complete"), rng)),
    ]
    adj = holm([c["p"] for _, c in secondary])
    secondary = [{"contrast": name, **c, "p_holm": p} for (name, c), p in zip(secondary, adj)]
    desc: dict = {}
    for ev in pc.EVIDENCE_LEVELS:
        for ins in pc.INSTRUCTIONS:
            rs = sel(ev, ins)
            if not rs:
                continue
            entry = {f: round(float(np.mean(list(cm(rs, f).values()))), 3)
                     for f in ("complete", "clean", "addressed", "invented", "damaged", "code_consistent",
                               "asked_unanswerable", "asked_any")}
            entry["unchanged"] = round(float(np.mean(list(case_means(rs, lambda r: r["unchanged"]).values()))), 3)
            entry["read_diff"] = round(float(np.mean(list(case_means(rs, lambda r: r["read_diff"]).values()))), 3)
            desc[pc.arm(ev, ins)] = entry
    by_model, by_judge, by_read = {}, {}, {}
    for m in sorted({r["model"] for r in rows}):
        by_model[m] = {pc.arm(ev, ins): round(float(np.mean(list(cm([r for r in sel(ev, ins) if r["model"] == m], "complete").values()) or [float("nan")])), 3)
                       for ev in pc.EVIDENCE_LEVELS for ins in pc.INSTRUCTIONS}
    for j in sorted({r["judge"] for r in rows}):
        by_judge[j] = {ev: round(float(np.mean(list(cm([r for r in sel(ev) if r["judge"] == j], "complete").values()) or [float("nan")])), 3)
                       for ev in pc.EVIDENCE_LEVELS}
    for ev in ("E_code", "E1"):
        for flag in (True, False):
            rs = [r for r in sel(ev) if r["read_diff"] == flag]
            if rs:
                by_read[f"{ev}/read_diff={flag}"] = {"outputs": len({(r['model'], r['instruction'], r['run'], r['case']) for r in rs}),
                                                     "complete": round(float(np.mean(list(cm(rs, "complete").values()))), 3)}
    cost: dict = defaultdict(lambda: defaultdict(list))
    seen = set()
    for r in rows:
        k = (r["model"], r["evidence"], r["instruction"], r["run"], r["case"])
        if k in seen:
            continue
        seen.add(k)
        if r.get("cost_usd") is not None:
            cost[r["model"]][pc.arm(r["evidence"], r["instruction"])].append((r["cost_usd"], r["seconds"]))
    cost_out = {m: {a: {"runs": len(v), "usd": round(float(np.mean([x for x, _ in v])), 4),
                        "seconds": round(float(np.mean([s for _, s in v])), 1)} for a, v in arms.items()}
                for m, arms in cost.items()}
    return {"primary": primary, "secondary": secondary, "descriptive": desc, "by_model_complete": by_model,
            "by_judge_complete": by_judge, "by_diff_read": by_read, "cost": cost_out}


def smoke_round3() -> None:
    """Round-3 A2 clean-fix means through this aggregation must match round3-analysis.json."""
    bench = json.loads((pc.PROC / "benchmark-a2.json").read_text())["records"]
    judg = {}
    for f in (pc.PROC / "judgments-a2-round3.json",):
        judg.update(json.loads(f.read_text()))
    labels = {}
    for key, rows in judg.items():
        judge = key.split(":", 1)[0]
        for r in rows:
            labels[(judge, r["model"], r["effort"], r["condition"], str(r["run"]), r["case"])] = r
    ref = json.loads((RESULTS / "round3-analysis.json").read_text())["descriptive"]["a2/edit"]
    ok = True
    for cond in ("compact_problems", "skill_inline", "three_sentences_r3", "v0.2.0_r3"):
        rows = []
        for rec in bench:
            if rec["condition"] != cond:
                continue
            for judge in ("claude", "codex"):
                j = labels.get((judge, rec["model"], rec["effort"], cond, str(rec["run"]), rec["case"]))
                if j:
                    rows.append({"case": rec["case"], "model": f"{rec['model']}@{rec['effort']}", "judge": judge, **outcomes(j)})
        for judge, key in (("claude", "cleanfix_claude"), ("codex", "cleanfix_codex")):
            got = round(float(np.mean(list(case_means([r for r in rows if r["judge"] == judge], lambda r: r["clean"]).values()))), 3)
            flag = "ok" if abs(got - ref[cond][key]) < 0.0015 else "MISMATCH"
            ok &= flag == "ok"
            print(f"{cond:<20} {judge:<7} {got:.3f} vs {ref[cond][key]:.3f} {flag}")
    raise SystemExit(0 if ok else 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke-round3", action="store_true")
    o = ap.parse_args()
    if o.smoke_round3:
        smoke_round3()
    records = json.loads((pc.PROC / "pilot-records.json").read_text())["records"]
    judgments = json.loads((pc.PROC / "pilot-judgments.json").read_text())
    rows = join(records, judgments)
    result = analyze(rows)
    (RESULTS / "pilot-analysis.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"primary": result["primary"], "secondary": result["secondary"]}, indent=1))


if __name__ == "__main__":
    main()
