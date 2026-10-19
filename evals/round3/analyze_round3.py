#!/usr/bin/env python3
"""Analyze round 3 exactly as evals/round3/PLAN.md specifies.

Reads the scored outputs (evals/results/benchmark.json and, when present, the private A2
records) and the round-3 judgments (judgments-round3.json and judgments-a2-round3.json),
then reports:

1. the nine primary contrasts, each between conditions run in round 3, with exact sign
   tests and Holm adjustment across the nine;
2. the equivalence check for skill_inline against the v0.2.0 rerun (paired case-bootstrap
   90% interval of the difference against a margin of 0.10);
3. drift: each rerun condition against its round-2 original (secondary, unadjusted);
4. descriptive outcomes per condition and judge for all nine conditions;
5. test-retest agreement between the original labels and the round-3 labels on outputs
   of the five round-2 conditions.

Aggregation follows the report: runs are averaged within a model configuration, the seven
configurations get equal weight, and judged scores average the two judges for tests.
Writes aggregate numbers only to evals/results/round3-analysis.json.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/round3/analyze_round3.py
Smoke test on the original data (no round-3 runs needed), which should reproduce the
report's A1 numbers for the compact instruction and v0.2.0:
  python3 evals/round3/analyze_round3.py --tag "" \\
      --alias compact_problems=three_sentences,skill_inline=v0.2.0,three_sentences_r3=three_sentences,v0.2.0_r3=v0.2.0 \
      --out /tmp/smoke.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
PROCESSED = DATA / "Processed/polish-open-source-prose"
RESULTS = REPO / "evals/results"

CONDS = ["no_skill", "one_sentence", "three_sentences", "v0.1.0", "v0.2.0",
         "compact_problems", "skill_inline", "three_sentences_r3", "v0.2.0_r3"]
ORIGINAL = CONDS[:5]
MODELS = [("claude-opus-5-5", "high"), ("claude-opus-4-6", "high"), ("claude-sonnet-5-5", "high"),
          ("gpt-6.1-sol", "high"), ("gpt-6-astra", "high"), ("gpt-6-astra", "low"), ("gpt-6-luna", "max")]
JUDGES = ["claude", "codex"]
# (label, condition, comparator, outcome); outcome is "a1_keep", "a1_cleanfix", or "a2_cleanfix".
PRIMARY = [(f"{a} vs {b}: {o}", a, b, o)
           for a, b in (("compact_problems", "three_sentences_r3"), ("compact_problems", "v0.2.0_r3"),
                        ("skill_inline", "v0.2.0_r3"))
           for o in ("a1_keep", "a1_cleanfix", "a2_cleanfix")]
# Secondary: how far a rerun moved from its round-2 original (time, harness version, models).
DRIFT = [(f"{a} vs {b}: {o}", a, b, o)
         for a, b in (("three_sentences_r3", "three_sentences"), ("v0.2.0_r3", "v0.2.0"))
         for o in ("a1_keep", "a1_cleanfix", "a2_cleanfix")]
MARGIN = 0.10
BOOT = 5000
SEED = 20261019


def sign_test(w: int, l: int) -> float:
    n = w + l
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n)


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=ps.__getitem__)
    adj, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def weighted_kappa(a: list[float], b: list[float], levels=(0, 0.5, 1)) -> float | None:
    if not a:
        return None
    k, idx = len(levels), {v: i for i, v in enumerate(levels)}
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1 / len(a)
    rows = [sum(r) for r in obs]
    cols = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = lambda i, j: (i - j) ** 2 / (k - 1) ** 2  # noqa: E731
    num = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k))
    den = sum(w(i, j) * rows[i] * cols[j] for i in range(k) for j in range(k))
    return None if den == 0 else round(1 - num / den, 3)


def okey(r: dict) -> tuple:
    return (r["set"], r["model"], r["effort"], r["condition"], r["run"], r["case"])


def load_judgments(tag: str) -> dict[str, dict[tuple, dict]]:
    """judge -> output key -> label row."""
    names = (f"judgments-{tag}.json", f"judgments-a2-{tag}.json") if tag else ("judgments.json", "judgments-a2.json")
    out: dict[str, dict[tuple, dict]] = {j: {} for j in JUDGES}
    for f in (RESULTS / names[0], PROCESSED / names[1]):
        if not f.exists():
            continue
        for key, rows in json.loads(f.read_text()).items():
            judge = key.split(":", 1)[0]
            for r in rows:
                out[judge][okey(r)] = r
    return out


def load_records(alias: dict[str, str]) -> list[dict]:
    records = json.loads((RESULTS / "benchmark.json").read_text())["records"]
    a2 = PROCESSED / "benchmark-a2.json"
    if a2.exists():
        records += json.loads(a2.read_text())["records"]
    records = [r for r in records if r["set"] in ("a1", "a2") and r["mode"] != "provenance"]
    for new, src in alias.items():  # smoke test only: pretend a source condition is a new one
        records += [{**r, "condition": new} for r in records if r["condition"] == src]
    return records


def per_output(records: list[dict], judg: dict) -> list[dict]:
    """Attach the outcome values each analysis needs to every output."""
    out, missing = [], []
    for r in records:
        row = {**{k: r[k] for k in ("set", "model", "effort", "condition", "run", "case", "mode")},
               "unchanged": r["unchanged"], "pass": r["pass"]}
        src = dict(r, condition=r.get("_judged_as", r["condition"]))
        for j in JUDGES:
            lab = judg[j].get(okey(src))
            if r["mode"] == "keep":
                if r["unchanged"]:
                    row[f"harmful_{j}"] = False
                elif lab is None:
                    missing.append((j, okey(r)))
                else:
                    row[f"harmful_{j}"] = bool(lab["harmful"])
            else:
                if lab is None:
                    missing.append((j, okey(r)))
                    continue
                a, i, d = float(lab["addressed"]), bool(lab["invented"]), bool(lab["damaged"])
                row.update({f"addressed_{j}": a, f"invented_{j}": i, f"damaged_{j}": d,
                            f"cleanfix_{j}": a * (not i) * (not d)})
        out.append(row)
    if missing:
        # A missing label is never counted as harmless or as zero; the analysis stops instead.
        raise SystemExit(f"{len(missing)} required judgments are missing, e.g. {missing[:3]}")
    return out


def case_means(rows: list[dict], set_name: str, mode: str, value) -> dict[str, dict[str, float]]:
    """condition -> case -> mean over configurations of the mean over runs (equation 2)."""
    cell: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        if r["set"] == set_name and (r["mode"] == "keep") == (mode == "keep"):
            cell[r["condition"]][r["case"]][(r["model"], r["effort"])].append(value(r))
    out = {}
    for cond, cases in cell.items():
        out[cond] = {}
        for case, by_model in cases.items():
            if set(by_model) != set(MODELS):
                raise SystemExit(f"{set_name}/{case}/{cond}: configurations missing: {set(MODELS) - set(by_model)}")
            out[cond][case] = mean(mean(v) for v in by_model.values())
    return out


OUTCOMES = {
    "a1_keep": ("a1", "keep", lambda r: float(r["pass"])),
    "a1_cleanfix": ("a1", "edit", lambda r: mean(r[f"cleanfix_{j}"] for j in JUDGES)),
    "a2_cleanfix": ("a2", "edit", lambda r: mean(r[f"cleanfix_{j}"] for j in JUDGES)),
}


def paired_boot(x: dict[str, float], y: dict[str, float], rng: random.Random) -> tuple[float, list[float], list[float]]:
    cases = sorted(x)
    diffs = [x[c] - y[c] for c in cases]
    boots = sorted(mean(rng.choice(diffs) for _ in diffs) for _ in range(BOOT))
    q = lambda p: boots[min(BOOT - 1, int(p * BOOT))]  # noqa: E731
    return mean(diffs), [q(0.05), q(0.95)], [q(0.025), q(0.975)]


def contrasts(rows: list[dict], family: list[tuple], adjust: bool) -> list[dict]:
    rng = random.Random(SEED)
    means = {o: case_means(rows, *OUTCOMES[o][:2], OUTCOMES[o][2]) for o in OUTCOMES if any(
        r["set"] == OUTCOMES[o][0] for r in rows)}
    res = []
    for label, a, b, o in family:
        if o not in means or a not in means[o] or b not in means[o]:
            res.append({"contrast": label, "status": "not available"})
            continue
        x, y = means[o][a], means[o][b]
        w = sum(x[c] > y[c] + 1e-12 for c in x)
        l = sum(x[c] < y[c] - 1e-12 for c in x)
        d, ci90, ci95 = paired_boot(x, y, rng)
        res.append({"contrast": label, "cases": len(x), "mean_a": round(mean(x.values()), 3),
                    "mean_b": round(mean(y.values()), 3), "diff": round(d, 3), "wins": w, "losses": l,
                    "p": sign_test(w, l), "ci90": [round(v, 3) for v in ci90], "ci95": [round(v, 3) for v in ci95]})
    avail = [r for r in res if "p" in r]
    if adjust:
        for r, ph in zip(avail, holm([r["p"] for r in avail])):
            r["p_holm"] = ph
    for r in avail:
        if r["contrast"].startswith("skill_inline vs v0.2.0_r3"):
            lo, hi = r["ci90"]
            r["equivalent_within_margin"] = -MARGIN < lo and hi < MARGIN
    return res


def describe(rows: list[dict]) -> dict:
    out: dict = {}
    for s in ("a1", "a2"):
        for mode in ("keep", "edit"):
            sub = [r for r in rows if r["set"] == s and (r["mode"] == "keep") == (mode == "keep")]
            if not sub:
                continue
            for cond in CONDS:
                cr = [r for r in sub if r["condition"] == cond]
                if not cr:
                    continue
                def agg(f):  # equal weight per configuration, runs averaged first
                    return round(mean(mean(f(r) for r in cr if (r["model"], r["effort"]) == m) for m in MODELS), 3)
                d = {"unchanged": agg(lambda r: float(r["unchanged"]))}
                if mode == "keep":
                    d["literal_pass"] = agg(lambda r: float(r["pass"]))
                    for j in JUDGES:
                        d[f"harmful_{j}"] = agg(lambda r, j=j: float(r[f"harmful_{j}"]))
                else:
                    for j in JUDGES:
                        for k in ("addressed", "cleanfix", "invented", "damaged"):
                            d[f"{k}_{j}"] = agg(lambda r, j=j, k=k: float(r[f"{k}_{j}"]))
                out.setdefault(f"{s}/{mode}", {})[cond] = d
    return out


def retest(new: dict, old: dict) -> dict:
    out = {}
    for j in JUDGES:
        shared = [k for k in new[j] if k in old[j] and k[3] in ORIGINAL]
        keep = [k for k in shared if "harmful" in new[j][k]]
        edit = [k for k in shared if "addressed" in new[j][k]]
        out[j] = {
            "outputs": len(shared),
            "harmful_kappa": kappa([old[j][k]["harmful"] for k in keep], [new[j][k]["harmful"] for k in keep]),
            "addressed_weighted_kappa": weighted_kappa([float(old[j][k]["addressed"]) for k in edit],
                                                       [float(new[j][k]["addressed"]) for k in edit]),
            "invented_kappa": kappa([old[j][k]["invented"] for k in edit], [new[j][k]["invented"] for k in edit]),
            "damaged_kappa": kappa([old[j][k]["damaged"] for k in edit], [new[j][k]["damaged"] for k in edit]),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="round3", help='judgment files to analyze; "" means the original ones')
    ap.add_argument("--alias", default="", help="smoke test only: new=source,... duplicates source outputs")
    ap.add_argument("--out", default=str(RESULTS / "round3-analysis.json"))
    o = ap.parse_args()
    alias = dict(p.split("=") for p in o.alias.split(",") if p)
    records = load_records(alias)
    for r in records:
        if r["condition"] in alias:
            r["_judged_as"] = alias[r["condition"]]
    judg = load_judgments(o.tag)
    rows = per_output(records, judg)
    result = {"plan": "evals/round3/PLAN.md", "judgments": o.tag or "original", "alias": alias,
              "primary": contrasts(rows, PRIMARY, adjust=True),
              "drift": contrasts(rows, DRIFT, adjust=False), "descriptive": describe(rows)}
    if o.tag:
        result["retest_vs_original"] = retest(judg, load_judgments(""))
    Path(o.out).write_text(json.dumps(result, indent=1) + "\n")
    for name in ("primary", "drift"):
        print(f"\n{name}\n{'contrast':48} {'n':>3} {'a':>6} {'b':>6} {'diff':>6}  W:L    p      Holm   90% CI")
        for r in result[name]:
            if "p" not in r:
                print(f"{r['contrast']:48} not available")
                continue
            eq = "  equivalent" if r.get("equivalent_within_margin") else ""
            ph = f"{r['p_holm']:.4f}" if "p_holm" in r else "  -   "
            print(f"{r['contrast']:48} {r['cases']:>3} {r['mean_a']:6.3f} {r['mean_b']:6.3f} {r['diff']:+6.3f}  "
                  f"{r['wins']}:{r['losses']:<3} {r['p']:.4f} {ph} {r['ci90']}{eq}")
    print(f"wrote {o.out}")


if __name__ == "__main__":
    main()
