#!/usr/bin/env python3
"""Trial of the diff truncation rule on the two largest A2 diffs (PILOT_DESIGN §4).

For each case, five round-3 outputs (v0.2.0 rerun and compact rerun, mixed models) are
judged three ways by the chosen judges: the whole diff inline on stdin, the truncated
diff inline, and the whole diff as a file in the sandbox. Labels and token usage per
variant go to $POLISH_EVAL_DATA/Processed/polish-open-source-prose/truncation-trial/
(third-party text; outside Git); the summary printed has no text.

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/study/try_truncation.py [--judges sol,astra] [--cases a2-airflow-71403,a2-cpython-150425]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_pilot as jp  # noqa: E402
import pilot_common as pc  # noqa: E402
from truncate_diff import truncate  # noqa: E402

OUT = pc.PROC / "truncation-trial"
LABELS = ("addressed", "code_consistent", "invented", "damaged", "asked")


def pick_outputs(cid: str, n: int = 5) -> list[dict]:
    recs = [r for r in json.loads((pc.PROC / "benchmark-a2.json").read_text())["records"]
            if r["case"] == cid and r["condition"] in ("v0.2.0_r3", "three_sentences_r3")]
    rng = random.Random(f"trial/{cid}")
    rng.shuffle(recs)
    chosen = recs[:n]
    return [{"model": r["model"], "evidence": "E0", "instruction": r["condition"], "run": str(r["run"]), "case": cid,
             "output": r["output"], "note": r.get("note", "")} for r in chosen]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judges", default="sol,astra")
    ap.add_argument("--cases", default="a2-airflow-71403,a2-cpython-150425")
    ap.add_argument("--max-line", type=int, default=300)
    ap.add_argument("--max-file-lines", type=int, default=120)
    ap.add_argument("--max-total", type=int, default=120_000)
    o = ap.parse_args()
    cases = pc.read_cases()
    OUT.mkdir(parents=True, exist_ok=True)
    results = json.loads((OUT / "results.json").read_text()) if (OUT / "results.json").exists() else {}
    for cid in o.cases.split(","):
        outs = pick_outputs(cid)
        for r in outs:
            r["label"] = jp.label_for(r)
        rendered = "\n\n".join(jp.render_output(r) for r in outs)
        full = pc.diff_text(cid)
        short = truncate(full, o.max_line, o.max_file_lines, o.max_total)
        static = dict(original=cases[cid]["input"], review=pc.review_body(cid), ci=pc.ci_summary(cid))
        variants = {
            "full_inline": {"prompt": jp.PROMPT.format(**static, diff_block=jp.DIFF_INLINE.format(diff=full), outputs=rendered),
                            "diff_as_file": False},
            "truncated_inline": {"prompt": jp.PROMPT.format(**static, diff_block=jp.DIFF_INLINE.format(diff=short), outputs=rendered),
                                 "diff_as_file": False},
            "full_file": {"prompt": jp.PROMPT.format(**static, diff_block=jp.DIFF_FILE, outputs=rendered), "diff_as_file": True},
        }
        for judge in o.judges.split(","):
            for name, v in variants.items():
                key = f"{judge}:{cid}:{name}"
                if key in results and results[key].get("labels"):
                    continue
                p = {"key": key, "prompt": v["prompt"], "prompt_file_mode": v["prompt"], "diff_as_file": v["diff_as_file"],
                     "diff": full, "large": True, "items": outs}
                print(f"{key}: {len(v['prompt']):,} chars", flush=True)
                text, usage = jp.call_codex(judge, p)
                rows = jp.parse(text)
                by_label = {r.get("label"): r for r in rows}
                labels = {r["label"]: by_label.get(r["label"]) for r in outs}
                results[key] = {"usage": usage, "complete": all(labels.values()), "labels": labels, "raw": text[:4000]}
                (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")
                print(f"  -> {sum(1 for v_ in labels.values() if v_)}/{len(outs)} labels; input {usage['input_tokens']:,} "
                      f"(cached {usage['cached_input_tokens']:,}), output {usage['output_tokens']:,}, {usage['seconds']}s, rc {usage['returncode']}",
                      flush=True)
    # Summary: agreement of each variant with full_inline, per judge and case, and usage.
    print("\nvariant agreement with full_inline (per label, over the five outputs):")
    for judge in o.judges.split(","):
        for cid in o.cases.split(","):
            base = results.get(f"{judge}:{cid}:full_inline", {}).get("labels") or {}
            for name in ("truncated_inline", "full_file"):
                other = results.get(f"{judge}:{cid}:{name}", {}).get("labels") or {}
                agree = {lab: sum(1 for k in base if base.get(k) and other.get(k) and base[k].get(lab) == other[k].get(lab))
                         for lab in LABELS}
                n = sum(1 for k in base if base.get(k) and other.get(k))
                u = results.get(f"{judge}:{cid}:{name}", {}).get("usage", {})
                print(f"  {judge:<6}{cid:<22}{name:<18} n={n} " + " ".join(f"{lab}={agree[lab]}" for lab in LABELS)
                      + f"  tokens in={u.get('input_tokens', 0):,} out={u.get('output_tokens', 0):,}")
            u = results.get(f"{judge}:{cid}:full_inline", {}).get("usage", {})
            print(f"  {judge:<6}{cid:<22}{'full_inline':<18} tokens in={u.get('input_tokens', 0):,} out={u.get('output_tokens', 0):,} rc={u.get('returncode')}")


if __name__ == "__main__":
    main()
