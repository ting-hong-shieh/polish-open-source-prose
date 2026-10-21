#!/usr/bin/env python3
"""Agreement between the pilot judges, and what the judging cost (PILOT_DESIGN §4-5).

Reads pilot-records.json, pilot-judgments.json (judge_pilot.py), $PILOT_ROOT/judge-usage.jsonl
and judge-excluded.json. Prints a report and writes
$POLISH_EVAL_DATA/Processed/polish-open-source-prose/pilot-judge-agreement.json (numbers
only, no third-party text).

Per judge: calls by kind (batch, smaller batch, single output), attempts, retries, file-route
and truncated calls, outcomes, tokens (input, cached input, output, reasoning), seconds, outputs
judged and left. Agreement, on the outputs every judge labelled: raw agreement, pairwise Cohen's
kappa (binary labels, `asked` with three categories, complete clean fix), linear and quadratic
weighted kappa and Krippendorff's alpha (ordinal) for `addressed`, Fleiss' kappa across the
judges (addressed as three categories), all overall and per evidence level; how often all
judges agree on complete clean fix; each judge's label rates, to see who is more lenient.

The judges are those with at least one judgment in the file, in judge_pilot.py's order (astra,
sol, luna, gemini-pro, gemini-flash), unless --judges names them. The Gemini comparison on the
100-output sample has its own report (judge_compare_sample.py report).

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/study/judge_agreement.py [--judges a,b] [--out PATH]
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_pilot as jp  # noqa: E402
import pilot_common as pc  # noqa: E402

JUDGES = list(jp.JUDGES)  # candidates; main() keeps those with judgments unless --judges names them
CATS = {"addressed": [0.0, 0.5, 1.0], "code_consistent": [False, True], "invented": [False, True],
        "damaged": [False, True], "asked": ["none", "answerable", "unanswerable"], "complete": [False, True]}
LABELS = list(CATS)


def value(row: dict, label: str):
    if label == "complete":
        return bool(float(row["addressed"]) == 1 and row["code_consistent"] and not row["invented"] and not row["damaged"])
    return float(row[label]) if label == "addressed" else row[label]


def cohen(a: list, b: list, cats: list, weights: str | None = None) -> float | None:
    k = len(cats)
    idx = {c: i for i, c in enumerate(cats)}
    o = np.zeros((k, k))
    for x, y in zip(a, b):
        o[idx[x], idx[y]] += 1
    o /= o.sum()
    e = np.outer(o.sum(1), o.sum(0))
    i, j = np.indices((k, k))
    w = {None: (i != j).astype(float), "linear": np.abs(i - j) / (k - 1), "quadratic": ((i - j) / (k - 1)) ** 2}[weights]
    de = (w * e).sum()
    return None if de == 0 else float(1 - (w * o).sum() / de)


def fleiss(rows: list[list], cats: list) -> float | None:
    idx = {c: i for i, c in enumerate(cats)}
    n = np.zeros((len(rows), len(cats)))
    for u, vals in enumerate(rows):
        for v in vals:
            n[u, idx[v]] += 1
    m = n.sum(1)[0]
    p_i = ((n * n).sum(1) - m) / (m * (m - 1))
    p_j = n.sum(0) / n.sum()
    pe = (p_j ** 2).sum()
    return None if pe == 1 else float((p_i.mean() - pe) / (1 - pe))


def alpha_ordinal(rows: list[list], cats: list) -> float | None:
    """Krippendorff's alpha, ordinal metric, units with at least two values."""
    k = len(cats)
    idx = {c: i for i, c in enumerate(cats)}
    o = np.zeros((k, k))
    for vals in rows:
        if len(vals) < 2:
            continue
        cnt = Counter(idx[v] for v in vals)
        for c in cnt:
            for d in cnt:
                o[c, d] += cnt[c] * (cnt[d] - (c == d)) / (len(vals) - 1)
    n_c = o.sum(1)
    n = n_c.sum()
    delta = np.zeros((k, k))
    for c in range(k):
        for d in range(k):
            lo, hi = min(c, d), max(c, d)
            delta[c, d] = (n_c[lo:hi + 1].sum() - (n_c[c] + n_c[d]) / 2) ** 2
    de = (np.outer(n_c, n_c) * delta).sum()
    return None if de == 0 else float(1 - (n - 1) * (o * delta).sum() / de)


def r3(x):
    return None if x is None else round(x, 3)


def agreement(items: list[dict], judges: list[str]) -> dict:
    """items: {judge: row} per output, every judge present."""
    out = {"n": len(items)}
    for lab in LABELS:
        cats = CATS[lab]
        vals = {j: [value(it[j], lab) for it in items] for j in judges}
        d: dict = {"pairwise": {}}
        for a, b in itertools.combinations(judges, 2):
            p = {"raw": r3(float(np.mean([x == y for x, y in zip(vals[a], vals[b])]))),
                 "kappa": r3(cohen(vals[a], vals[b], cats))}
            if lab == "addressed":
                p["kappa_linear"] = r3(cohen(vals[a], vals[b], cats, "linear"))
                p["kappa_quadratic"] = r3(cohen(vals[a], vals[b], cats, "quadratic"))
            d["pairwise"][f"{a}-{b}"] = p
        units = [[vals[j][u] for j in judges] for u in range(len(items))]
        d["fleiss_kappa"] = r3(fleiss(units, cats))
        d["all_agree"] = r3(float(np.mean([len(set(u)) == 1 for u in units])))
        if lab == "addressed":
            d["alpha_ordinal"] = r3(alpha_ordinal(units, cats))
        if lab in ("complete", "code_consistent", "invented", "damaged"):
            yes = Counter(sum(u) for u in units)
            d["judges_saying_true"] = {str(k): yes.get(k, 0) for k in range(len(judges) + 1)}
        out[lab] = d
    return out


def rates(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {}
    add = Counter(float(r["addressed"]) for r in rows)
    ask = Counter(r["asked"] for r in rows)
    return {"n": n, "addressed_mean": r3(float(np.mean([float(r["addressed"]) for r in rows]))),
            "addressed": {str(k): r3(add.get(k, 0) / n) for k in CATS["addressed"]},
            **{lab: r3(sum(bool(r[lab]) for r in rows) / n) for lab in ("code_consistent", "invented", "damaged")},
            "asked": {k: r3(ask.get(k, 0) / n) for k in CATS["asked"]},
            "complete": r3(sum(value(r, "complete") for r in rows) / n)}


def usage_summary(usage: list[dict], judge: str) -> dict:
    us = [u for u in usage if u.get("judge") == judge]
    calls = {}
    for u in us:
        calls.setdefault((u["key"], u.get("kind", "batch")), []).append(u)
    by_kind = Counter(kind for _, kind in calls)
    tok = {k: int(sum(u.get(k, 0) for u in us)) for k in ("input_tokens", "cached_input_tokens", "output_tokens",
                                                           "reasoning_output_tokens")}
    ok = [u for u in us if u.get("outcome") in ("complete", "partial")]
    return {"attempts": len(us), "calls": {"batch": by_kind.get("batch", 0), "sub-batch": by_kind.get("sub-batch", 0),
                                           "single": by_kind.get("single", 0)},
            "retries": sum(1 for u in us if u.get("attempt", 1) > 1),
            "file_route_attempts": sum(1 for u in us if u.get("diff_as_file")),
            "truncated_attempts": sum(1 for u in us if u.get("diff_truncated")),
            "outcomes": dict(Counter(u.get("outcome") for u in us)),
            "rate_limited_attempts": sum(1 for u in us if u.get("rate_limited")),
            "tokens": tok, "tokens_failed_attempts": {k: int(sum(u.get(k, 0) for u in us if u not in ok)) for k in tok},
            "seconds": round(sum(u.get("seconds", 0) for u in us), 1),
            "mean_seconds_per_attempt": round(float(np.mean([u.get("seconds", 0) for u in us])), 1) if us else None,
            "first_started": min((u["started"] for u in us if u.get("started")), default=None),
            "last_started": max((u["started"] for u in us if u.get("started")), default=None)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, default=jp.RECORDS)
    ap.add_argument("--judgments", type=Path, default=jp.OUT)
    ap.add_argument("--usage", type=Path, default=jp.USAGE)
    ap.add_argument("--out", type=Path, default=pc.PROC / "pilot-judge-agreement.json")
    ap.add_argument("--judges", default="", help="comma-separated (default: every judge with a judgment in the file)")
    o = ap.parse_args()
    excl = json.loads(jp.EXCLUDED.read_text()) if jp.EXCLUDED.exists() else {"cases": []}
    records = [r for r in json.loads(o.records.read_text())["records"] if r["case"] not in excl["cases"]]
    judgments = json.loads(o.judgments.read_text())
    judges = [j for j in o.judges.split(",") if j] or [j for j in JUDGES if any(k.startswith(f"{j}:") for k in judgments)]
    if set(judges) - set(jp.JUDGES):
        raise SystemExit(f"unknown judge(s): {', '.join(sorted(set(judges) - set(jp.JUDGES)))}")
    usage = [json.loads(line) for line in o.usage.read_text().splitlines() if line.strip()] if o.usage.exists() else []

    items, per_judge_rows, stale = [], {j: [] for j in judges}, Counter()
    for r in records:
        it = dict(r, label=jp.label_for(r), output_sha=jp.output_hash(r))
        got = {}
        for j in judges:
            rows = judgments.get(jp.result_key(j, it))
            if rows and rows[0].get("output_sha") == it["output_sha"]:
                got[j] = rows[0]
                per_judge_rows[j].append({**rows[0], "evidence": r["evidence"]})
            elif rows:
                stale[j] += 1
        it["judged"] = got
        items.append(it)

    summary = {"records": len(records), "excluded_cases": excl["cases"], "judges": {}}
    for j in judges:
        rows = per_judge_rows[j]
        models = sorted({r["judge_model"] for r in rows if r.get("judge_model")})
        summary["judges"][j] = {"model": models[0] if len(models) == 1 else models or jp.JUDGES[j][0],
                                "effort": jp.JUDGES[j][1], "outputs_judged": len(rows),
                                "outputs_left": len(records) - len(rows), "stale_judgments": stale[j],
                                "judgment_kinds": dict(Counter(r.get("kind") for r in rows)),
                                "judged_with_diff_as_file": sum(1 for r in rows if r.get("diff_as_file")),
                                "judged_with_diff_truncated": sum(1 for r in rows if r.get("diff_truncated")),
                                "usage": usage_summary(usage, j),
                                "rates": rates(rows),
                                "rates_by_evidence": {ev: rates([r for r in rows if r["evidence"] == ev])
                                                      for ev in pc.EVIDENCE_LEVELS}}
    present = [j for j in judges if per_judge_rows[j]]
    full = [{j: it["judged"][j] for j in present} | {"_ev": it["evidence"], "_case": it["case"]}
            for it in items if all(j in it["judged"] for j in present)]
    summary["agreement_judges"] = present
    if len(present) >= 2:
        summary["agreement"] = agreement(full, present)
        summary["agreement_by_evidence"] = {ev: agreement([x for x in full if x["_ev"] == ev], present)
                                            for ev in pc.EVIDENCE_LEVELS}
        summary["by_case"] = {}
        for c in sorted({x["_case"] for x in full}):
            xs = [x for x in full if x["_case"] == c]
            summary["by_case"][c] = {
                "n": len(xs),
                **{f"{lab}_all_agree": r3(float(np.mean([len({value(x[j], lab) for j in present}) == 1 for x in xs])))
                   for lab in ("complete", "code_consistent", "addressed", "damaged")},
                "complete_rate": {j: r3(float(np.mean([value(x[j], "complete") for x in xs]))) for j in present}}
        summary["pairwise_direction"] = {}
        for a, b in itertools.combinations(present, 2):
            summary["pairwise_direction"][f"{a}-{b}"] = {
                lab: {f"{a}_higher": sum(1 for x in full if float(value(x[a], lab)) > float(value(x[b], lab))),
                      f"{b}_higher": sum(1 for x in full if float(value(x[a], lab)) < float(value(x[b], lab)))}
                for lab in ("addressed", "code_consistent", "invented", "damaged", "complete")}
            summary["pairwise_direction"][f"{a}-{b}"]["all_five_labels_equal"] = sum(
                1 for x in full if all(value(x[a], lab) == value(x[b], lab) for lab in LABELS[:5]))
            summary["pairwise_direction"][f"{a}-{b}"]["identical_judge_note"] = sum(
                1 for x in full if x[a].get("note") is not None and x[a].get("note") == x[b].get("note"))
    jp.write_atomic(o.out, json.dumps(summary, indent=1) + "\n")
    report(summary, present)
    print(f"\nwrote {o.out}")


def report(s: dict, present: list[str]) -> None:
    w = max([6, *map(len, s["judges"])])  # judge column width
    print(f"{s['records']} outputs (excluded cases: {', '.join(s['excluded_cases']) or 'none'})\n")
    print(f"{'judge':<{w}} {'judged':>6} {'left':>4} {'attempts':>8} {'batch':>5} {'sub':>4} {'single':>6} {'retry':>5} "
          f"{'file':>4} {'trunc':>5} {'input':>11} {'cached':>11} {'output':>9} {'reason':>9} {'seconds':>8}")
    for j, d in s["judges"].items():
        u = d["usage"]
        print(f"{j:<{w}} {d['outputs_judged']:>6} {d['outputs_left']:>4} {u['attempts']:>8} {u['calls']['batch']:>5} "
              f"{u['calls']['sub-batch']:>4} {u['calls']['single']:>6} {u['retries']:>5} {u['file_route_attempts']:>4} "
              f"{u['truncated_attempts']:>5} {u['tokens']['input_tokens']:>11,} {u['tokens']['cached_input_tokens']:>11,} "
              f"{u['tokens']['output_tokens']:>9,} {u['tokens']['reasoning_output_tokens']:>9,} {u['seconds']:>8,.0f}")
        print(f"{'':<{w}} outcomes {u['outcomes']}")
    print("\nlabel rates per judge (all evidence levels)")
    for j, d in s["judges"].items():
        r = d["rates"]
        if r:
            print(f"  {j:<{w}} addressed mean {r['addressed_mean']} {r['addressed']}; code_consistent {r['code_consistent']}; "
                  f"invented {r['invented']}; damaged {r['damaged']}; asked {r['asked']}; complete {r['complete']}")
    if "agreement" not in s:
        return
    a = s["agreement"]
    pairs = list(a["addressed"]["pairwise"])
    print(f"\nagreement on {a['n']} outputs judged by {', '.join(present)}")
    pw = max([22, *(len(p) + 8 for p in pairs)])
    print(f"{'label':<16}" + "".join(f"{p + ' raw/k':>{pw}}" for p in pairs) + f"{'Fleiss':>8}{'all agree':>10}")
    for lab in LABELS:
        d = a[lab]
        print(f"{lab:<16}" + "".join(f"{d['pairwise'][p]['raw']:>{pw - 10}} / {d['pairwise'][p]['kappa']!s:>6}  " for p in pairs)
              + f"{d['fleiss_kappa']!s:>8}{d['all_agree']:>10}")
    print("addressed weighted kappa (linear / quadratic): "
          + "; ".join(f"{p} {a['addressed']['pairwise'][p]['kappa_linear']} / {a['addressed']['pairwise'][p]['kappa_quadratic']}"
                      for p in pairs) + f"; Krippendorff alpha ordinal {a['addressed']['alpha_ordinal']}")
    print(f"complete clean fix, number of judges saying yes: {a['complete']['judges_saying_true']}")
    print("\nby evidence level: Fleiss kappa (all-agree share)")
    print(f"{'label':<16}" + "".join(f"{ev:>16}" for ev in pc.EVIDENCE_LEVELS))
    for lab in LABELS:
        print(f"{lab:<16}" + "".join(f"{str(s['agreement_by_evidence'][ev][lab]['fleiss_kappa']) + ' (' + str(s['agreement_by_evidence'][ev][lab]['all_agree']) + ')':>16}"
                                     for ev in pc.EVIDENCE_LEVELS))
    print("\npairwise: outputs where the first / second judge gave the higher value; all five labels equal; identical judge note")
    for pair, d in s["pairwise_direction"].items():
        print(f"  {pair:<{2 * w - 1}}" + "; ".join(f"{lab} {list(v.values())[0]}/{list(v.values())[1]}" for lab, v in d.items()
                                          if isinstance(v, dict)) + f"; all five equal {d['all_five_labels_equal']}"
              + f"; identical note {d['identical_judge_note']}")
    low = sorted(s["by_case"].items(), key=lambda kv: kv[1]["complete_all_agree"])[:4]
    print("cases with the lowest all-agree share on complete clean fix: "
          + "; ".join(f"{c} {d['complete_all_agree']} (rates {d['complete_rate']})" for c, d in low))
    print("\ncomplete clean fix rate per judge by evidence level")
    for j, d in s["judges"].items():
        print(f"  {j:<{w}}" + "".join(f"{ev:>8} {d['rates_by_evidence'][ev].get('complete')!s:<6}" for ev in pc.EVIDENCE_LEVELS))


if __name__ == "__main__":
    main()
