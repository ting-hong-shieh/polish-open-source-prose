#!/usr/bin/env python3
"""Share of pull requests above the diff-size limit (STUDY_PLAN: a case whose diff exceeds
1,500 lines, added plus removed, is excluded), for two sets:

(a) every pull request with at least one positive in a classifier results file
    (`classify_comments.py --run ... --output`), and
(b) every landed pull request of the pulled repositories, a proxy for the keep pool: state
    MERGED in pulls.jsonl, plus closed pull requests that a committer landed by pushing
    (apache/spark: a "Merged to/into ..." comment; nodejs/node: "Landed in <sha>").

Sizes come from batched GraphQL (`additions deletions changedFiles` per pull request number),
one process, one token; on a rate limit it sleeps to the reset. The output is appended as
each batch arrives, and (repo, number) pairs already in it are skipped, so a rerun resumes.
Before the first call it waits while another GitHub-heavy study script is running.

The size is the pull request's final size at fetch time. The sampling rule applies to the
diff at the selected comment's timestamp, so this is a proxy.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/study/pr_sizes.py --fetch all --report \
         --results .../classifier-full-12/results-haiku.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
RAW = DATA / "Raw/polish-open-source-prose/pr-comments-2026"
OUT_DIR = DATA / "Processed/polish-open-source-prose/classifier-full-12"
LIMIT = 1500
LANDED = {"apache/spark": re.compile(r"^\s*(thanks[^\n]{0,40}\n+\s*)?merged (in)?to\b|\bmerged (in)?to (master|branch|\d)",
                                     re.I | re.M),
          "nodejs/node": re.compile(r"^Landed in [0-9a-f]{7}", re.M)}
OTHERS = re.compile(r"(select_repositories|collect_pr_comments)\.py")


def wait_for_others() -> None:
    """Wait while a Python process runs another GitHub-heavy study script (shell loops that
    merely mention the name are ignored)."""
    while True:
        ps = subprocess.run(["ps", "-eo", "pid=,comm=,args="], capture_output=True, text=True).stdout
        busy = [l.strip() for l in ps.split("\n") if l.split()[1:2] and l.split()[1].startswith("python")
                and OTHERS.search(l)]
        if not busy:
            return
        print(f"waiting for {len(busy)} GitHub-heavy process(es): {busy[0][:120]}", file=sys.stderr, flush=True)
        time.sleep(120)


def graphql(query: str) -> tuple[dict, list]:
    """Return (data, errors). Per-alias errors such as NOT_FOUND come back with partial data."""
    attempt = 0
    while True:
        p = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"], capture_output=True, text=True)
        try:
            body = json.loads(p.stdout)
        except json.JSONDecodeError:
            body = None
        errs = (body or {}).get("errors") or []
        text = (p.stderr + json.dumps(errs)).lower()
        if any(e.get("type") == "RATE_LIMITED" for e in errs) or "rate limit" in text:
            try:
                rl = json.loads(subprocess.run(["gh", "api", "rate_limit"], capture_output=True, text=True).stdout)
                wait = max(30, rl["resources"]["graphql"]["reset"] - int(time.time()) + 15)
            except Exception:
                wait = 600
            print(f"  rate limit: sleeping {wait}s", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        if body and body.get("data") is not None:
            return body["data"], errs
        attempt += 1
        if attempt <= 8:
            wait = 60 * attempt
            print(f"  retry in {wait}s: {(p.stderr or p.stdout).strip()[:160]}", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError((p.stderr or p.stdout).strip()[:500])


def landed_pool() -> dict[tuple[str, int], str]:
    """(b): (repo, number) -> 'merged' or 'landed_comment'."""
    pool = {}
    for d in sorted(RAW.iterdir()):
        if not (d / "counts.json").exists():
            continue
        repo = d.name.replace("__", "/")
        prs = {json.loads(l)["number"]: json.loads(l) for l in (d / "pulls.jsonl").read_text().split("\n") if l}
        for n, pr in prs.items():
            if pr["state"] == "MERGED":
                pool[(repo, n)] = "merged"
        if repo in LANDED:
            for line in (d / "issue_comments.jsonl").read_text().split("\n"):
                if not line:
                    continue
                c = json.loads(line)
                n = c["pr_number"]
                if n in prs and prs[n]["state"] == "CLOSED" and LANDED[repo].search(c["body"] or ""):
                    pool.setdefault((repo, n), "landed_comment")
    return pool


def positives(results: Path) -> Counter:
    """(a): (repo, number) -> number of positive comments (last parsed answer per id)."""
    last = {}
    for line in results.read_text().split("\n"):
        if line:
            r = json.loads(line)
            if isinstance((r.get("answer") or {}).get("criticizes_text"), bool):
                last[r["id"]] = r
    out = Counter()
    for r in last.values():
        if r["answer"]["criticizes_text"]:
            out[(r["repo"], int(re.search(r"/pull/(\d+)", r["url"]).group(1)))] += 1
    return out


def fetch(targets: list[tuple[str, int]], out: Path, batch: int) -> None:
    done = set()
    if out.exists():
        for line in out.read_text().split("\n"):
            if line:
                r = json.loads(line)
                done.add((r["repo"], r["number"]))
    todo = defaultdict(list)
    for repo, n in sorted(set(targets) - done):
        todo[repo].append(n)
    total = sum(map(len, todo.values()))
    print(f"sizes: {len(done)} already fetched, {total} to fetch, batches of {batch}", flush=True)
    if not total:
        return
    wait_for_others()
    got, t0 = 0, time.time()
    with out.open("a") as f:
        for repo, numbers in todo.items():
            owner, name = repo.split("/")
            for i in range(0, len(numbers), batch):
                chunk = numbers[i:i + batch]
                parts = " ".join(f"p{n}: pullRequest(number: {n}) {{ number additions deletions changedFiles state "
                                 f"mergedAt }}" for n in chunk)
                data, errs = graphql(f'query {{ repository(owner: "{owner}", name: "{name}") {{ {parts} }} '
                                     f'rateLimit {{ remaining resetAt cost }} }}')
                repo_data = data.get("repository") or {}
                stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                for n in chunk:
                    pr = repo_data.get(f"p{n}")
                    row = {"repo": repo, "number": n, "fetched_at": stamp}
                    if pr:
                        row.update(additions=pr["additions"], deletions=pr["deletions"], changedFiles=pr["changedFiles"],
                                   state=pr["state"], mergedAt=pr["mergedAt"])
                    else:
                        row["missing"] = [e.get("message") for e in errs if f"p{n}" in (e.get("path") or [])][:1] or True
                    f.write(json.dumps(row) + "\n")
                f.flush()
                got += len(chunk)
                rl = data.get("rateLimit") or {}
                print(f"{repo} {got}/{total} remaining={rl.get('remaining')} cost={rl.get('cost')} "
                      f"elapsed={time.time() - t0:.0f}s", flush=True)


def share(rows: list[dict], weights: dict | None = None) -> dict:
    sized = [r for r in rows if "additions" in r]
    w = (lambda r: weights[(r["repo"], r["number"])]) if weights else (lambda r: 1)
    total = sum(w(r) for r in sized)
    above = sum(w(r) for r in sized if r["additions"] + r["deletions"] > LIMIT)
    lines = sorted(r["additions"] + r["deletions"] for r in sized)
    return {"n": len(sized), "weight": total, "above": above, "share_above": round(above / total, 4) if total else None,
            "median_lines": lines[len(lines) // 2] if lines else None, "missing": len(rows) - len(sized)}


def report(out: Path, results: Path, report_path: Path) -> None:
    sizes = {}
    for line in out.read_text().split("\n"):
        if line:
            r = json.loads(line)
            sizes[(r["repo"], r["number"])] = r
    pos = positives(results)
    pool = landed_pool()
    rep = {"limit_lines": LIMIT, "sizes_file": str(out), "results_file": str(results),
           "note": "final PR size at fetch time (additions + deletions) as a proxy; the sampling rule applies to "
                   "the diff at the selected comment's timestamp",
           "a_positive_prs": {}, "a_positive_comments": {}, "b_landed_prs": {}, "b_by_source": {}}
    repos = sorted({k[0] for k in pos} | {k[0] for k in pool})
    for repo in repos + ["total"]:
        def sel(keys):
            return [sizes.get(k, {"repo": k[0], "number": k[1]}) for k in keys if repo == "total" or k[0] == repo]
        rep["a_positive_prs"][repo] = share(sel(pos))
        rep["a_positive_comments"][repo] = share(sel(pos), pos)
        rep["b_landed_prs"][repo] = share(sel(pool))
    for src in ("merged", "landed_comment"):
        rep["b_by_source"][src] = share([sizes.get(k, {"repo": k[0], "number": k[1]}) for k, v in pool.items() if v == src])
    report_path.write_text(json.dumps(rep, indent=1))
    print(f"limit {LIMIT} lines (additions + deletions, final PR size)")
    print(f"{'repository':<24}{'(a) PRs w/ positive':>22}{'(a) by comment':>16}{'(b) landed PRs':>18}")
    for repo in repos + ["total"]:
        a, ac, b = rep["a_positive_prs"][repo], rep["a_positive_comments"][repo], rep["b_landed_prs"][repo]
        fmt = lambda s: f"{s['above']}/{s['weight']} {s['share_above']:.1%}" if s["share_above"] is not None else "-"
        print(f"{repo:<24}{fmt(a):>22}{fmt(ac):>16}{fmt(b):>18}")
    print("(b) by source:", {k: f"{v['above']}/{v['n']} {v['share_above']:.1%}" for k, v in rep["b_by_source"].items() if v["n"]})
    print("missing sizes:", {k: rep[k]["total"]["missing"] for k in ("a_positive_prs", "b_landed_prs")})
    print(f"-> {report_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=OUT_DIR / "results-haiku.jsonl")
    ap.add_argument("--out", type=Path, default=OUT_DIR / "pr-sizes.jsonl")
    ap.add_argument("--fetch", choices=["landed", "positives", "all"], default=None)
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--report", action="store_true")
    o = ap.parse_args()
    if o.fetch:
        targets = []
        if o.fetch in ("landed", "all"):
            targets += list(landed_pool())
        if o.fetch in ("positives", "all"):
            targets += list(positives(o.results))
        fetch(targets, o.out, o.batch)
    if o.report:
        report(o.out, o.results, o.out.with_name("pr-sizes-report.json"))


if __name__ == "__main__":
    main()
