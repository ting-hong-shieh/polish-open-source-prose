#!/usr/bin/env python3
"""Aggregate the benchmark, draw the report figures, and write the report tables.

Reads evals/results/benchmark.json and evals/results/judgments.json, plus the private A2
records, the review-thread labels, and the raw run logs (for cost) under $POLISH_EVAL_DATA.
Writes evals/results/analysis.json (aggregate numbers only, safe to publish),
docs/report/figures/*.pdf, and docs/report/generated/*.tex.

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/analyze_benchmark.py
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
PROCESSED = DATA / "Processed/polish-open-source-prose"
RUNS = DATA / "Exports/polish-open-source-prose/eval-runs-2026-10-04/round2"
FIG = REPO / "docs/report/figures"
GEN = REPO / "docs/report/generated"

CONDS = ["no_skill", "one_sentence", "three_sentences", "v0.1.0", "v0.2.0"]
COND_LABEL = {"no_skill": "No skill", "one_sentence": "One sentence", "three_sentences": "Three sentences",
              "v0.1.0": "Skill v0.1.0", "v0.2.0": "Skill v0.2.0"}
MODELS = [("claude-opus-5-5", "high"), ("claude-opus-4-6", "high"), ("claude-sonnet-5-5", "high"),
          ("gpt-6.1-sol", "high"), ("gpt-6-astra", "high"), ("gpt-6-astra", "low"), ("gpt-6-luna", "max")]
MODEL_LABEL = {("claude-opus-5-5", "high"): "Opus 5.5", ("claude-opus-4-6", "high"): "Opus 4.6",
               ("claude-sonnet-5-5", "high"): "Sonnet 5.5", ("gpt-6.1-sol", "high"): "GPT-6.1 Sol",
               ("gpt-6-astra", "high"): "GPT-6 Astra (high)", ("gpt-6-astra", "low"): "GPT-6 Astra (low)",
               ("gpt-6-luna", "max"): "GPT-6 Luna (max)"}
JUDGES = {"claude": ("claude-opus-5-5", "high"), "codex": ("gpt-6.1-sol", "high")}
JUDGE_LABEL = {"claude": "Opus 5.5 judge", "codex": "GPT-6.1 Sol judge"}
# Validated categorical order (dataviz reference palette); markers carry identity too.
COLOR = dict(zip(CONDS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))
MARKER = dict(zip(CONDS, ["o", "s", "D", "v", "^"]))
INK, MUTED, GRID = "#1f2328", "#59636e", "#d8dee4"
RNG = np.random.default_rng(20261005)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})


def mkey(r: dict) -> tuple:
    return (r["model"], r["effort"])


def binom_two_sided(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def weighted_kappa(a: list[float], b: list[float], levels=(0, 0.5, 1)) -> float | None:
    if not a:
        return None
    idx = {v: i for i, v in enumerate(levels)}
    k = len(levels)
    obs = np.zeros((k, k))
    for x, y in zip(a, b):
        obs[idx[x], idx[y]] += 1
    obs /= obs.sum()
    exp = np.outer(obs.sum(1), obs.sum(0))
    w = np.array([[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)])
    return float(1 - (w * obs).sum() / (w * exp).sum())


def case_bootstrap(per_case: dict[str, list[float]], n: int = 2000) -> tuple[float, float, float]:
    """Mean over all scores, with a 95% interval from resampling cases."""
    cases = list(per_case)
    sums = np.array([sum(per_case[c]) for c in cases])
    counts = np.array([len(per_case[c]) for c in cases])
    point = sums.sum() / counts.sum()
    draws = RNG.integers(0, len(cases), size=(n, len(cases)))
    boots = sums[draws].sum(1) / counts[draws].sum(1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(point), float(lo), float(hi)


def load() -> tuple[list[dict], dict, dict]:
    bench = json.loads((REPO / "evals/results/benchmark.json").read_text())
    records = bench["records"]
    a2 = PROCESSED / "benchmark-a2.json"
    if a2.exists():
        records += json.loads(a2.read_text())["records"]
    judgments = {}
    for f in (REPO / "evals/results/judgments.json", PROCESSED / "judgments-a2.json"):
        if f.exists():
            judgments.update(json.loads(f.read_text()))
    a2cases = {c["id"]: c for c in json.loads((PROCESSED / "heldout-a2-cases.json").read_text())["cases"]}
    return records, judgments, a2cases


def literal_tables(records: list[dict]) -> dict:
    """Pass rates per set, model, condition, and case kind (keep/edit), averaged over runs."""
    out: dict = defaultdict(lambda: defaultdict(dict))
    for s in ("main", "a1"):
        for m in MODELS:
            for c in CONDS:
                for kind in ("keep", "edit"):
                    rs = [r for r in records if r["set"] == s and mkey(r) == m and r["condition"] == c
                          and (r["mode"] == "keep") == (kind == "keep") and r["mode"] != "provenance"]
                    if rs:
                        out[s][MODEL_LABEL[m]][f"{c}/{kind}"] = round(sum(r["pass"] for r in rs) / len(rs), 3)
    return out


def per_case_scores(records: list[dict], s: str, kind: str, value) -> dict:
    """{condition: {model: {case: mean over runs}}}."""
    acc: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in records:
        if r["set"] != s or r["mode"] == "provenance" or (r["mode"] == "keep") != (kind == "keep"):
            continue
        v = value(r)
        if v is not None:
            acc[r["condition"]][mkey(r)][r["case"]].append(v)
    return {c: {m: {k: sum(v) / len(v) for k, v in cs.items()} for m, cs in ms.items()} for c, ms in acc.items()}


def sign_tests(scores: dict) -> list[dict]:
    """v0.2.0 against each other condition, per model and pooled by case (mean over models)."""
    rows = []
    for other in [c for c in CONDS if c != "v0.2.0"]:
        if other not in scores or "v0.2.0" not in scores:
            continue
        for m in MODELS + ["pooled"]:
            if m == "pooled":
                cases = set.intersection(*(set(scores["v0.2.0"][x]) for x in scores["v0.2.0"]))
                a = {k: np.mean([scores["v0.2.0"][x][k] for x in scores["v0.2.0"]]) for k in cases}
                b = {k: np.mean([scores[other][x][k] for x in scores[other]]) for k in cases}
            else:
                if m not in scores["v0.2.0"] or m not in scores[other]:
                    continue
                a, b = scores["v0.2.0"][m], scores[other][m]
            common = set(a) & set(b)
            wins = int(sum(a[k] > b[k] + 1e-9 for k in common))
            losses = int(sum(b[k] > a[k] + 1e-9 for k in common))
            rows.append({"vs": other, "model": "pooled" if m == "pooled" else MODEL_LABEL[m],
                         "wins": wins, "losses": losses, "n": len(common), "p": binom_two_sided(wins, losses)})
    return rows


def judged(judgments: dict) -> dict:
    """{(judge, set, model, effort, condition, run, case, kind): verdict}."""
    out = {}
    for key, rows in judgments.items():
        judge = key.split(":", 1)[0]
        for r in rows:
            out[(judge, r["set"], r["model"], r["effort"], r["condition"], r["run"], r["case"], r["kind"])] = r
    return out


def clean_fix(v: dict) -> float:
    """The addressed score, counted only when the revision neither invented nor damaged anything."""
    return 0.0 if v["invented"] or v["damaged"] else float(v["addressed"])


def cell_mean(cells: dict) -> float:
    """Mean over (model, case) cells, each the mean over that model's runs, so every model weighs the same."""
    return round(float(np.mean([np.mean(v) for v in cells.values()])), 3)


def judge_summary(records: list[dict], J: dict, a2cases: dict) -> dict:
    res: dict = {"edit": {}, "keep": {}, "agreement": {}, "self_preference": {}}
    # Edit cases in A1 and A2: every output was judged.
    for judge in JUDGES:
        for s in ("a1", "a2", "a2-judgeable"):
            real = "a2" if s == "a2-judgeable" else s
            for c in CONDS:
                cells = {f: defaultdict(list) for f in ("addressed", "clean", "invented", "damaged", "unchanged")}
                for r in records:
                    if r["set"] != real or r["mode"] in ("keep", "provenance") or r["condition"] != c:
                        continue
                    if s == "a2-judgeable" and not a2cases[r["case"]]["judgeable_from_text"]:
                        continue
                    v = J.get((judge, r["set"], r["model"], r["effort"], c, r["run"], r["case"], "edit"))
                    if v:
                        cell = (mkey(r), r["case"])
                        cells["addressed"][cell].append(float(v["addressed"]))
                        cells["clean"][cell].append(clean_fix(v))
                        cells["invented"][cell].append(bool(v["invented"]))
                        cells["damaged"][cell].append(bool(v["damaged"]))
                        cells["unchanged"][cell].append(bool(r["unchanged"]))
                if cells["addressed"]:
                    res["edit"].setdefault(judge, {}).setdefault(s, {})[c] = {
                        "n": sum(len(v) for v in cells["addressed"].values()),
                        **{f: cell_mean(cs) for f, cs in cells.items()}}
    # Keep cases: unchanged outputs count as not harmful; changed outputs were judged.
    for judge in JUDGES:
        for s in ("main", "a1"):
            for c in CONDS:
                changed, harm = defaultdict(list), defaultdict(list)
                for r in records:
                    if r["set"] != s or r["mode"] != "keep" or r["condition"] != c:
                        continue
                    v = J.get((judge, s, r["model"], r["effort"], c, r["run"], r["case"], "keep"))
                    changed[(mkey(r), r["case"])].append(not r["unchanged"])
                    harm[(mkey(r), r["case"])].append(bool(not r["unchanged"] and v and v["harmful"]))
                if changed:
                    res["keep"].setdefault(judge, {}).setdefault(s, {})[c] = {
                        "n": sum(len(v) for v in changed.values()), "changed": cell_mean(changed),
                        "harmful": cell_mean(harm)}
    # Agreement between the two judges on the same outputs.
    pairs = defaultdict(lambda: ([], []))
    for (judge, *rest), v in J.items():
        if judge != "claude":
            continue
        other = J.get(("codex", *rest))
        if not other:
            continue
        kind = rest[-1]
        fields = ("harmful",) if kind == "keep" else ("addressed", "invented", "damaged")
        for f in fields:
            pairs[f][0].append(v[f])
            pairs[f][1].append(other[f])
    for f, (a, b) in pairs.items():
        if f == "addressed":
            a, b = [float(x) for x in a], [float(x) for x in b]
            res["agreement"][f] = {"n": len(a), "exact": round(float(np.mean([x == y for x, y in zip(a, b)])), 3),
                                   "weighted_kappa": round(weighted_kappa(a, b), 3)}
        else:
            a, b = [bool(x) for x in a], [bool(x) for x in b]
            res["agreement"][f] = {"n": len(a), "exact": round(float(np.mean([x == y for x, y in zip(a, b)])), 3),
                                   "kappa": None if kappa(a, b) is None else round(kappa(a, b), 3),
                                   "rate_claude": round(float(np.mean(a)), 3), "rate_codex": round(float(np.mean(b)), 3)}
    # Self-preference: does a judge score its own model's edit outputs higher than the other judge does,
    # by more than it does for other models' outputs?
    for judge, own in JUDGES.items():
        other = "codex" if judge == "claude" else "claude"
        gaps = {"own": [], "others": []}
        for (j, s, model, effort, c, run, case, kind), v in J.items():
            if j != judge or kind != "edit":
                continue
            w = J.get((other, s, model, effort, c, run, case, kind))
            if w:
                gaps["own" if (model, effort) == own else "others"].append(float(v["addressed"]) - float(w["addressed"]))
        res["self_preference"][judge] = {k: {"n": len(g), "mean_gap": round(float(np.mean(g)), 3) if g else None}
                                         for k, g in gaps.items()}
    return res


def costs() -> dict:
    """Mean cost and time per run on the held-out sets, where every configuration used one layout."""
    out: dict = defaultdict(dict)
    for m in MODELS:
        for c in CONDS:
            secs, usd, tin, tout = [], [], [], []
            for s in ("runs-a1", "runs-a2"):
                if m[0].startswith("claude"):
                    for f in glob.glob(str(RUNS / s / "claude" / m[0] / c / "run*" / "*" / "meta.json")):
                        meta = json.loads(Path(f).read_text())
                        if meta.get("rc") == 0:
                            secs.append(meta["seconds"])
                            usd.append(meta["cost_usd"])
                else:
                    tag = "gpt-6-astra@low" if m == ("gpt-6-astra", "low") else m[0]
                    for f in glob.glob(str(RUNS / s / "codex" / tag / c / "*" / "status.json")):
                        st = json.loads(Path(f).read_text())
                        if st.get("returncode") != 0:
                            continue
                        secs.append(st["elapsed_seconds"])
                        i = o = 0
                        for line in (Path(f).parent / "events.jsonl").read_text().splitlines():
                            if '"turn.completed"' in line:
                                u = json.loads(line)["usage"]
                                i += u.get("input_tokens", 0)
                                o += u.get("output_tokens", 0)
                        tin.append(i)
                        tout.append(o)
            if secs:
                row = {"runs": len(secs), "seconds": round(float(np.mean(secs)), 1)}
                if usd:
                    row["usd"] = round(float(np.mean(usd)), 4)
                if tin:
                    row["input_tokens"] = round(float(np.mean(tin)))
                    row["output_tokens"] = round(float(np.mean(tout)))
                out[MODEL_LABEL[m]][c] = row
    return out


def disclosures(records: list[dict], a2cases: dict) -> dict:
    """A2 descriptions with an AI disclosure line: was that line kept exactly, altered, or deleted?"""
    tools = re.compile(r"ChatGPT|Codex|OpenAI|Claude|Gemini|Copilot", re.I)
    out: dict = {}
    for c in CONDS:
        row = Counter()
        for r in records:
            case = a2cases.get(r["case"]) if r["set"] == "a2" else None
            if not case or r["condition"] != c:
                continue
            want = [l.strip() for l in case["input"].splitlines() if l.strip().startswith("Generated-by:")]
            if not want:
                continue
            got = [l.strip() for l in r["output"].splitlines() if l.strip().startswith("Generated-by")]
            row["outputs"] += 1
            if all(w in got for w in want):
                row["kept"] += 1
            elif not got:
                row["deleted"] += 1
            else:
                row["altered"] += 1
                if set(m.lower() for m in tools.findall(" ".join(got))) - set(m.lower() for m in tools.findall(" ".join(want))):
                    row["tool_added"] += 1
        out[c] = dict(row)
    out["cases"] = sum(any(l.strip().startswith("Generated-by:") for l in c["input"].splitlines()) for c in a2cases.values())
    return out


def critique_counts() -> dict:
    rows = [json.loads(line) for line in (PROCESSED / "review-thread-labels.jsonl").read_text().splitlines() if line]
    types = Counter(t for r in rows for t in r["critique_types"])
    return {"threads": len(rows), "about_prose": sum(r["critique_about_prose"] for r in rows),
            "types": dict(types.most_common()),
            "author_edited_text": sum(r["author_response"] in ("edited_description", "renamed_title", "edited_both")
                                      for r in rows),
            "author_response": dict(Counter(r["author_response"] for r in rows).most_common())}


# ---------- figures ----------

def save(fig, name: str) -> None:
    fig.savefig(FIG / name)
    if os.environ.get("PREVIEW_DIR"):  # PNG copies for a quick look; not part of the report
        fig.savefig(Path(os.environ["PREVIEW_DIR"]) / name.replace(".pdf", ".png"), dpi=160)
    plt.close(fig)


def fig_critiques(cc: dict) -> None:
    names = {"no_evidence": "No evidence for a claim", "ai_disclosure": "AI use not disclosed",
             "unrelated_changes": "Unrelated changes", "description_mismatch": "Description does not match code",
             "verbose": "Too long or padded", "hard_to_understand": "Hard to understand",
             "overclaim": "Overclaims", "narrating_comments": "Comments narrate the code",
             "canned_triage": "Canned or templated reply", "fabricated": "Fabricated content",
             "other": "Other"}
    items = sorted(((k, v) for k, v in cc["types"].items() if k != "other"), key=lambda kv: kv[1])
    items = [("other", cc["types"].get("other", 0))] + items
    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    y = np.arange(len(items))
    ax.barh(y, [v for _, v in items], color="#2a78d6", height=0.6)
    for i, (_, v) in enumerate(items):
        ax.text(v + 0.4, i, str(v), va="center", color=INK, fontsize=7)
    ax.set_yticks(y, [names.get(k, k) for k, _ in items])
    ax.set_xlabel(f"Threads (n = {cc['threads']}; one thread can have several)")
    ax.xaxis.grid(True, color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save(fig, "critiques.pdf")


def fig_dots(lit: dict, kind: str, name: str, xlabel: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.7), sharey=True)
    labels = [MODEL_LABEL[m] for m in MODELS]
    for ax, s, title in zip(axes, ("main", "a1"), ("Development set (49 cases)", "Held-out set A1 (24 cases)")):
        for j, c in enumerate(CONDS):
            xs = [lit[s].get(lab, {}).get(f"{c}/{kind}") for lab in labels]
            ys = [i + (j - 2) * 0.12 for i in range(len(labels))]
            pts = [(x, y) for x, y in zip(xs, ys) if x is not None]
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=22, marker=MARKER[c], color=COLOR[c],
                       edgecolor="white", linewidth=0.6, label=COND_LABEL[c], zorder=3)
        for i in range(len(labels)):
            ax.axhline(i, color=GRID, lw=0.5, zorder=1)
        ax.set_xlim(-0.03, 1.03)
        ax.set_title(title, fontsize=8, color=INK, loc="left")
        ax.set_xlabel(xlabel)
    axes[0].set_yticks(range(len(labels)), labels)
    axes[0].invert_yaxis()
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, ncol=5, loc="upper center", frameon=False, fontsize=7, bbox_to_anchor=(0.55, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, name)


def fig_tradeoff(records: list[dict], boot: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.9), sharey=True)
    for ax, s, title in zip(axes, ("main", "a1"), ("Development set", "Held-out set A1")):
        for c in CONDS:
            kx, klo, khi = boot[s]["keep"][c]
            ex, elo, ehi = boot[s]["edit"][c]
            ax.errorbar(kx, ex, xerr=[[kx - klo], [khi - kx]], yerr=[[ex - elo], [ehi - ex]], fmt=MARKER[c],
                        color=COLOR[c], ms=6, mec="white", mew=0.6, elinewidth=0.8, capsize=0, zorder=3)
            ax.annotate(COND_LABEL[c], (kx, ex), xytext=(5, 4), textcoords="offset points", fontsize=7, color=INK)
        ax.set_xlim(0, 1.02)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("Clear text left unchanged (keep cases)")
        ax.set_title(title, fontsize=8, color=INK, loc="left")
        ax.grid(True, color=GRID, lw=0.5)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Edit cases passing literal checks")
    fig.tight_layout()
    save(fig, "tradeoff.pdf")


def fig_judged(js: dict) -> None:
    metrics = [("addressed", "Problem addressed"), ("clean", "Clean fix"), ("invented", "Added a fact"),
               ("damaged", "Damaged needed text")]
    sets = [s for s in ("a1", "a2") if any(s in js["edit"].get(j, {}) for j in JUDGES)]
    titles = {"a1": "A1 (12 edit cases)", "a2": "A2 (21 real pull requests)"}
    fig, axes = plt.subplots(len(sets), len(metrics), figsize=(6.8, 1.75 * len(sets) + 0.5), sharey=True,
                             squeeze=False)
    for row, s in enumerate(sets):
        for ax, (mtr, title) in zip(axes[row], metrics):
            for j, c in enumerate(CONDS):
                for judge, mk, off in (("claude", "o", -0.14), ("codex", "s", 0.14)):
                    v = js["edit"].get(judge, {}).get(s, {}).get(c)
                    if v:
                        ax.scatter(v[mtr], j + off, marker=mk, s=18, color=COLOR[c], edgecolor="white",
                                   linewidth=0.5, zorder=3)
            ax.set_xlim(-0.03, 1.03)
            ax.xaxis.grid(True, color=GRID, lw=0.5)
            ax.set_axisbelow(True)
            if row == 0:
                ax.set_title(title, fontsize=8, color=INK, loc="left")
            if row < len(sets) - 1:
                ax.tick_params(labelbottom=False)
        axes[row][0].set_ylabel(titles[s], fontsize=7.5, color=INK)
        axes[row][0].set_yticks(range(len(CONDS)), [COND_LABEL[c] for c in CONDS])
    axes[0][0].invert_yaxis()
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", ls="", color=MUTED, label="Opus 5.5 judge"),
               Line2D([], [], marker="s", ls="", color=MUTED, label="GPT-6.1 Sol judge")]
    fig.legend(handles=handles, ncol=2, loc="upper center", frameon=False, fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "judged.pdf")


def fig_harm(js: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.3), sharey=True)
    for ax, s, title in zip(axes, ("main", "a1"), ("Development set keep cases", "Held-out A1 keep cases")):
        y = np.arange(len(CONDS))
        ch = [js["keep"]["claude"][s][c]["changed"] for c in CONDS]
        ax.barh(y, ch, color=GRID, height=0.62, label="Changed the text")
        for judge, off, mk in (("claude", -0.13, "o"), ("codex", 0.13, "s")):
            ax.scatter([js["keep"][judge][s][c]["harmful"] for c in CONDS], y + off, marker=mk, s=20,
                       color=[COLOR[c] for c in CONDS], edgecolor="white", linewidth=0.5, zorder=3)
        for i, v in enumerate(ch):
            ax.text(v + 0.01, i, f"{v:.0%}", va="center", fontsize=6.5, color=MUTED)
        ax.set_xlim(-0.02, 1.05)
        ax.set_title(title, fontsize=8, color=INK, loc="left")
        ax.set_xlabel("Share of outputs")
    axes[0].set_yticks(range(len(CONDS)), [COND_LABEL[c] for c in CONDS])
    axes[0].invert_yaxis()
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [Patch(color=GRID, label="Changed text that should stay"),
               Line2D([], [], marker="o", ls="", color=MUTED, label="Harmful change (Opus 5.5 judge)"),
               Line2D([], [], marker="s", ls="", color=MUTED, label="Harmful change (GPT-6.1 Sol judge)")]
    fig.legend(handles=handles, ncol=3, loc="upper center", frameon=False, fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    save(fig, "harm.pdf")


# ---------- tables ----------

def pct(x) -> str:
    return "--" if x is None else f"{round(100 * x)}"


def tex_literal(lit: dict, s: str, caption: str, label: str) -> str:
    head = " & ".join(rf"\multicolumn{{2}}{{c}}{{{COND_LABEL[c]}}}" for c in CONDS)
    sub = " & ".join("keep & edit" for _ in CONDS)
    rows = []
    for m in MODELS:
        d = lit[s].get(MODEL_LABEL[m], {})
        rows.append(MODEL_LABEL[m] + " & " + " & ".join(f"{pct(d.get(f'{c}/keep'))} & {pct(d.get(f'{c}/edit'))}"
                                                        for c in CONDS) + r" \\")
    return (r"\begin{table*}[t]\centering\small" "\n" rf"\caption{{{caption}}}\label{{{label}}}" "\n"
            r"\begin{tabular}{l" + "rr" * len(CONDS) + "}\n\\toprule\n & " + head + r" \\" "\n"
            + "".join(rf"\cmidrule(lr){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(len(CONDS))) + "\n & " + sub
            + r" \\" "\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table*}\n")


def tex_signs(rows: list[dict]) -> str:
    measures = [("main", "keep", "Development, keep (literal)"), ("main", "edit", "Development, edit (literal)"),
                ("a1", "keep", "A1, keep (literal)"), ("a1", "edit", "A1, edit (literal)"),
                ("a1", "edit, clean fix", "A1, edit (judged clean fix)"),
                ("a2", "edit, clean fix", "A2, edit (judged clean fix)")]
    others = [c for c in CONDS if c != "v0.2.0"]
    body = []
    for s, kind, name in measures:
        cells = []
        for o in others:
            r = next((r for r in rows if r["set"] == s and r["kind"] == kind and r["vs"] == o), None)
            if r is None:
                cells.append("--")
                continue
            p = "<.001" if r["p"] < 0.001 else f"{r['p']:.3f}".lstrip("0")
            cells.append(f"{r['wins']}:{r['losses']} ({p})")
        body.append(name + " & " + " & ".join(cells) + r" \\")
    return (r"\begin{table}[t]\centering\small" "\n"
            r"\caption{Paired sign tests of v0.2.0 against each other condition: cases where v0.2.0 scored "
            r"better:worse (two-sided $p$). Each case's score is averaged over the seven configurations, their "
            r"runs, and, for judged scores, both judges; ties are dropped.}\label{tab:signs}" "\n"
            r"\begin{tabular}{lrrrr}" "\n\\toprule\n & " + " & ".join(COND_LABEL[o] for o in others)
            + r" \\" "\n\\midrule\n" + "\n".join(body) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")


def tex_judged(js: dict) -> str:
    sets = [s for s in ("a1", "a2") if s in js["edit"].get("claude", {})]
    names = {"a1": "A1 (12 cases)", "a2": "A2 (21 real pull requests)"}
    fields = ("addressed", "clean", "invented", "damaged")
    rows = []
    for s in sets:
        rows.append(rf"\multicolumn{{10}}{{l}}{{\emph{{{names[s]}}}}} \\")
        for c in CONDS:
            o, g = js["edit"]["claude"][s][c], js["edit"]["codex"][s][c]
            cells = []
            for f in fields:
                cells += [f"{o[f]:.2f}", f"{g[f]:.2f}"] if f in ("addressed", "clean") else [pct(o[f]), pct(g[f])]
            rows.append(r"\quad " + COND_LABEL[c] + " & " + " & ".join(cells) + f" & {pct(o['unchanged'])}" + r" \\")
    return (r"\begin{table*}[t]\centering\small" "\n"
            r"\caption{Judged edit cases. In each pair the first number is from the Opus 5.5 judge and the second "
            r"from the GPT-6.1 Sol judge. \emph{Addressed} and \emph{clean fix} are mean scores from 0 to 1; a clean "
            r"fix counts the addressed score only when the revision neither added a fact nor damaged needed text. "
            r"\emph{Added a fact}, \emph{damaged}, and \emph{unchanged} are percentages of outputs. Models weigh "
            r"equally; Claude runs are averaged first.}\label{tab:judged}" "\n"
            r"\begin{tabular}{lrrrrrrrrr}" "\n\\toprule\n"
            r" & \multicolumn{2}{c}{Addressed} & \multicolumn{2}{c}{Clean fix} & \multicolumn{2}{c}{Added a fact} "
            r"& \multicolumn{2}{c}{Damaged} & Unchanged \\" "\n"
            r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}" "\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table*}\n")


def tex_costs(cost: dict) -> str:
    rows = []
    for m in MODELS:
        d = cost.get(MODEL_LABEL[m], {})
        cells = []
        for c in ("no_skill", "three_sentences", "v0.2.0"):
            v = d.get(c)
            if not v:
                cells.append("-- & --")
                continue
            extra = f"\\${v['usd']:.3f}" if "usd" in v else f"{v['input_tokens'] / 1000:.1f}k"
            cells.append(f"{v['seconds']:.0f} & {extra}")
        rows.append(MODEL_LABEL[m] + " & " + " & ".join(cells) + r" \\")
    head = " & ".join(rf"\multicolumn{{2}}{{c}}{{{COND_LABEL[c]}}}" for c in ("no_skill", "three_sentences", "v0.2.0"))
    return (r"\begin{table}[t]\centering\small" "\n"
            r"\caption{Mean seconds and cost per run on the held-out sets. Claude cost is the API-equivalent "
            r"estimate that Claude Code reports, not a bill; for Codex the table gives input tokens.}\label{tab:cost}"
            "\n" r"\begin{tabular}{lrrrrrr}" "\n\\toprule\n & " + head + r" \\" "\n"
            r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}" "\n & s & cost & s & cost & s & cost \\\\\n"
            "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    GEN.mkdir(parents=True, exist_ok=True)
    records, judgments, a2cases = load()
    lit = literal_tables(records)

    boot: dict = defaultdict(lambda: defaultdict(dict))
    tests = []
    for s in ("main", "a1"):
        for kind in ("keep", "edit"):
            sc = per_case_scores(records, s, kind, lambda r: float(r["pass"]))
            for c in CONDS:
                per_case = defaultdict(list)
                for m, cs in sc.get(c, {}).items():
                    for k, v in cs.items():
                        per_case[k].append(v)
                boot[s][kind][c] = case_bootstrap(per_case)
            for row in sign_tests(sc):
                tests.append({**row, "set": s, "kind": kind})

    J = judged(judgments)
    js = judge_summary(records, J, a2cases) if J else {}
    # First A1 judging pass, before the judges were shown the editor's note to the author.
    hidden_path = REPO / "evals/results/judgments-a1-notes-hidden.json"
    if js and hidden_path.exists():
        H = judged(json.loads(hidden_path.read_text()))
        js["a1_notes_hidden"] = {j: v.get("a1", {}) for j, v in judge_summary(records, H, a2cases)["edit"].items()}
    # Pooled sign tests on judged edits, each output scored by the mean over both judges.
    if J:
        for s in ("a1", "a2"):
            for name, f in (("addressed", lambda v: float(v["addressed"])), ("clean fix", clean_fix)):
                def judged_score(r, s=s, f=f):
                    vs = [J.get((j, s, r["model"], r["effort"], r["condition"], r["run"], r["case"], "edit"))
                          for j in JUDGES]
                    vs = [f(v) for v in vs if v]
                    return sum(vs) / len(vs) if vs else None
                sc = per_case_scores(records, s, "edit", judged_score)
                for row in sign_tests(sc):
                    tests.append({**row, "set": s, "kind": f"edit, {name}"})

    cc = critique_counts()
    cost = costs()
    analysis = {"literal": lit, "bootstrap_95": {s: {k: v for k, v in d.items()} for s, d in boot.items()},
                "sign_tests": tests, "judges": js, "costs": cost, "review_threads": cc,
                "a2_disclosure_lines": disclosures(records, a2cases)}
    (REPO / "evals/results/analysis.json").write_text(json.dumps(analysis, indent=1) + "\n")

    fig_critiques(cc)
    fig_dots(lit, "keep", "keep.pdf", "Keep cases returned unchanged")
    fig_tradeoff(records, boot)
    if js:
        fig_judged(js)
        fig_harm(js)

    (GEN / "table-main.tex").write_text(tex_literal(
        lit, "main", "Development set: percentage of cases passing, by model and condition (mean over runs; "
        "19 keep and 28 edit cases; the 2 provenance cases are left out).", "tab:main"))
    (GEN / "table-a1.tex").write_text(tex_literal(
        lit, "a1", "Held-out set A1: percentage of cases passing literal checks (12 keep, 12 edit).", "tab:a1"))
    pooled = [t for t in tests if t["model"] == "pooled"]
    (GEN / "table-signs.tex").write_text(tex_signs(pooled))
    (GEN / "table-cost.tex").write_text(tex_costs(cost))
    if js:
        (GEN / "table-judged.tex").write_text(tex_judged(js))
    print(json.dumps({"bootstrap": analysis["bootstrap_95"], "pooled_tests": pooled,
                      "agreement": js.get("agreement"), "self_preference": js.get("self_preference")}, indent=1))


if __name__ == "__main__":
    main()
