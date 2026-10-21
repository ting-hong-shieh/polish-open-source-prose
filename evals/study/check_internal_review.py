#!/usr/bin/env python3
"""Internal-review exclusion check for the sampling frame (CASE_COLLECTION.md, step 1).

A repository is excluded from the pool if more than 25% of its pull requests created in the
window 2025-10-01..2026-09-30 were imported from an internal review system: their review
happened elsewhere (Phabricator, Gerrit, Google's Piper), so the GitHub thread does not hold
the review. The cases that prompted the rule: pytorch/executorch, whose pull requests carry
"Differential Revision" bodies exported from Meta's Phabricator, and golang/go, mirrored to
Gerrit. The rule is applied the same way to every repository in the frame: repository rule
v3's selected list (repo-selection/v3/selected.json) together with the twelve repositories
pulled first; three are in both (apache/airflow, django/django, rust-lang/rust), so the frame
has 37 repositories.

Markers, fixed (2026-10-21) before any count was looked at. A pull request counts as imported
if its body contains any of them:
- "Differential Revision:"  Phabricator (Meta; also Mozilla and older LLVM): an exported diff.
- "Pull Request resolved:"  Meta's fbshipit / ghstack export trailer.
- "fbshipit-source-id"      Meta ShipIt's export trailer (added: it is the trailer ShipIt
                            documents for every commit it exports, the same export path as the
                            two above).
- "Reviewed-on:"            Gerrit, with or without "Change-Id:".
- "PiperOrigin-RevId"       Google Piper, exported through Copybara.
- "Copybara"                Google Copybara.
- "COPYBARA_INTEGRATE_REVIEW"  Copybara's pull-request integration tag (added: the search
                            index may keep it as one token, so "Copybara" alone could miss it).
Recorded but not part of the rule: "Change-Id:" alone. Gerrit's commit-msg hook adds it, but
projects that review on GitHub also carry it in commit messages, so on its own it does not
show that review happened elsewhere.

Method, also fixed before running:
1. total = search API total_count of `repo:R is:pr created:2025-10-01..2026-09-30`.
2. Per marker, total_count of the same query with `"<marker>" in:body`.
3. Union of the markers: 0 if every count is 0; the one count if only one marker is nonzero;
   if two or more are nonzero, each pair's intersection is counted (`"a" "b" in:body`), and
   if every pair is 0 the union is the sum (pairwise disjoint sets have no higher overlaps).
4. The bodies of every pull request in the window are fetched through GraphQL and the
   markers matched exactly (case-insensitive substring) when (a) some pair overlaps, or
   (b) the sum of the marker counts is at least 5% of the total. The search index ignores
   punctuation and matches phrases, so "Reviewed-on:" also matches prose such as "reviewed
   on the list"; its counts are an upper bound, and the exact count decides near the
   threshold. When GraphQL is used, its total and union are the ones used.
5. share = union / total; excluded if share > 25%.
Search calls are spaced 2.5 s apart (limit 30/min); a 403/429 rate limit sleeps until the
search window resets. Every query string and the time it ran are recorded. Only counts and
pull request numbers are kept; no body text is written.

Limitation: the markers are read from pull request bodies. A mirror that signals itself only
through a bot comment (golang/go's Gerrit bot) is not detected by this check.

Writes $POLISH_EVAL_DATA/Processed/polish-open-source-prose/repo-selection/
internal-review-check.json and REPORT.md under internal-review-check/ (the per-query log
internal-review-check/queries.jsonl lets a rerun resume without repeating queries).

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python -I evals/study/check_internal_review.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
SEL = DATA / "Processed/polish-open-source-prose/repo-selection"
V3 = SEL / "v3/selected.json"
OUT_JSON = SEL / "internal-review-check.json"
OUT_DIR = SEL / "internal-review-check"

START, END = "2025-10-01", "2026-09-30"
THRESHOLD = 0.25
VERIFY_AT = 0.05
SEARCH_GAP_S = 2.5

MARKERS = [
    ("Differential Revision:", "Phabricator export (Meta, Mozilla, older LLVM)"),
    ("Pull Request resolved:", "Meta fbshipit / ghstack export trailer"),
    ("fbshipit-source-id", "Meta ShipIt export trailer"),
    ("Reviewed-on:", "Gerrit (with or without Change-Id:)"),
    ("PiperOrigin-RevId", "Google Piper via Copybara"),
    ("Copybara", "Google Copybara"),
    ("COPYBARA_INTEGRATE_REVIEW", "Copybara pull-request integration tag"),
]
DIAGNOSTIC = [("Change-Id:", "Gerrit Change-Id alone; recorded, not part of the rule")]

# The twelve pulled first (collect_pr_comments.py, hand-picked list of 2026-10-20).
HAND_PICKED = ["apache/airflow", "apache/datafusion", "apache/arrow", "python/cpython",
               "kubernetes/kubernetes", "rust-lang/rust", "pandas-dev/pandas", "numpy/numpy",
               "nodejs/node", "prometheus/prometheus", "apache/spark", "django/django"]

_last_search = 0.0


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def gh(*args: str, search: bool = False) -> str:
    """gh api; stdout must parse as JSON. Rate limits sleep until reset; transient errors retry."""
    global _last_search
    attempt = 0
    while True:
        if search:
            wait = SEARCH_GAP_S - (time.monotonic() - _last_search)
            if wait > 0:
                time.sleep(wait)
        p = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
        if search:
            _last_search = time.monotonic()
        if p.returncode == 0:
            try:
                json.loads(p.stdout)
                return p.stdout
            except json.JSONDecodeError as exc:
                p.stderr = f"truncated json: {exc}"
        err = p.stderr.lower()
        if "rate limit" in err or "ratelimit" in err or "http 429" in err or "http 403" in err:
            try:
                lim = json.loads(subprocess.run(["gh", "api", "rate_limit"], capture_output=True, text=True).stdout)
                res = lim["resources"]["search" if search else "graphql"]
                wait = max(10, res["reset"] - int(time.time()) + 5) if res["remaining"] == 0 else 60
            except Exception:
                wait = 90
            print(f"  rate limit: sleeping {wait}s ({p.stderr.strip()[:100]})", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        attempt += 1
        if attempt <= 6 and any(k in err for k in ("502", "503", "504", "timeout", "unexpected end", "connection",
                                                     "eof", "something went wrong", "truncated json")):
            wait = 60 * attempt
            print(f"  retry in {wait}s: {p.stderr.strip()[:120]}", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(p.stderr.strip()[:500])


def load_log() -> dict[str, dict]:
    path = OUT_DIR / "queries.jsonl"
    if not path.exists():
        return {}
    return {r["query"]: r for r in (json.loads(l) for l in path.read_text().splitlines() if l)}


LOG: dict[str, dict] = {}


def count(q: str) -> dict:
    """total_count of a pull request search; each query runs once (logged, reused on rerun)."""
    if q in LOG:
        return LOG[q]
    for attempt in range(4):
        at = now_iso()
        body = json.loads(gh("-X", "GET", "search/issues", "-f", f"q={q}", "-f", "per_page=1", search=True))
        if not body.get("incomplete_results"):
            break
        time.sleep(10)
    rec = {"query": q, "queried_at": at, "total_count": body["total_count"],
           "incomplete_results": bool(body.get("incomplete_results"))}
    with (OUT_DIR / "queries.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")
    LOG[q] = rec
    return rec


BODY_QUERY = """
query($owner:String!,$name:String!,$after:String){
  repository(owner:$owner,name:$name){
    pullRequests(first:100, orderBy:{field:CREATED_AT, direction:DESC}, after:$after){
      pageInfo{ hasNextPage endCursor }
      nodes{ number createdAt body }
    }
  }
}"""


def exact(repo: str) -> dict:
    """All pull request bodies in the window through GraphQL; markers matched as
    case-insensitive substrings. Keeps numbers only."""
    owner, name = repo.split("/")
    after, total, pages = None, 0, 0
    hits: dict[str, list[int]] = {m: [] for m, _ in MARKERS + DIAGNOSTIC}
    union: list[int] = []
    t0 = now_iso()
    while True:
        args = ["graphql", "-f", f"query={BODY_QUERY}", "-F", f"owner={owner}", "-F", f"name={name}"]
        if after:
            args += ["-F", f"after={after}"]
        page = json.loads(gh(*args))["data"]["repository"]["pullRequests"]
        pages += 1
        below = False
        for pr in page["nodes"]:
            day = pr["createdAt"][:10]
            if day > END:
                continue
            if day < START:
                below = True
                break
            total += 1
            body = (pr["body"] or "").lower()
            for m, _ in MARKERS + DIAGNOSTIC:
                if m.lower() in body:
                    hits[m].append(pr["number"])
            if any(m.lower() in body for m, _ in MARKERS):
                union.append(pr["number"])
        if below or not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return {"fetched_from": t0, "fetched_to": now_iso(), "pages": pages, "total": total,
            "per_marker": {m: len(v) for m, v in hits.items()}, "union": len(union),
            "matched_numbers": {m: v for m, v in hits.items() if v}, "union_numbers": union}


def frame() -> list[dict]:
    v3 = json.loads(V3.read_text())["selected"]
    rows = [{"repo": r["repo"], "in_v3": True, "v3_domain": r["domain"], "in_first_12": r["repo"] in HAND_PICKED}
            for r in v3]
    seen = {r["repo"] for r in rows}
    rows += [{"repo": r, "in_v3": False, "v3_domain": None, "in_first_12": True} for r in HAND_PICKED if r not in seen]
    return rows


def check(row: dict) -> dict:
    repo = row["repo"]
    base = f"repo:{repo} is:pr created:{START}..{END}"
    tot = count(base)
    markers = {m: count(f'{base} "{m}" in:body') for m, _ in MARKERS}
    diag = {m: count(f'{base} "{m}" in:body') for m, _ in DIAGNOSTIC}
    nonzero = [m for m, r in markers.items() if r["total_count"] > 0]
    pairs = []
    for i, a in enumerate(nonzero):
        for b in nonzero[i + 1:]:
            r = count(f'{base} "{a}" "{b}" in:body')
            pairs.append({"a": a, "b": b, **r})
    s = sum(markers[m]["total_count"] for m in nonzero)
    total = tot["total_count"]
    overlap = any(p["total_count"] > 0 for p in pairs)
    rec = {**row, "total_search": total, "total_query": base, "total_queried_at": tot["queried_at"],
           "markers": markers, "diagnostic": diag, "pairwise": pairs, "search_sum": s,
           "search_share_upper": round(s / total, 4) if total else None,
           "incomplete_results": any(r["incomplete_results"] for r in [tot, *markers.values(), *diag.values(), *pairs])}
    if overlap or (total and s / total >= VERIFY_AT):
        g = exact(repo)
        rec["graphql"] = g
        rec["total"], rec["union"] = g["total"], g["union"]
        rec["method"] = "graphql exact (" + ("pairs overlap" if overlap else f"search sum >= {VERIFY_AT:.0%}") + ")"
    else:
        rec["total"], rec["union"] = total, s
        rec["method"] = ("search: no marker" if not nonzero else
                         "search: one marker" if len(nonzero) == 1 else "search: sum, pairs disjoint")
    rec["share"] = round(rec["union"] / rec["total"], 4) if rec["total"] else None
    rec["excluded"] = bool(rec["total"]) and rec["union"] / rec["total"] > THRESHOLD
    rec["checked_from"] = min(r["queried_at"] for r in [tot, *markers.values()])
    rec["checked_to"] = now_iso()
    return rec


def report(rows: list[dict], started: str) -> str:
    lines = [
        "# Internal-review exclusion check", "",
        f"Run {started} to {now_iso()}. Window {START} to {END} by pull request creation date. "
        f"Frame: repository rule v3's {sum(r['in_v3'] for r in rows)} selected repositories together with "
        f"the first twelve pulled; {sum(r['in_v3'] and r['in_first_12'] for r in rows)} are in both, so "
        f"{len(rows)} repositories. A repository is excluded if more than {THRESHOLD:.0%} of its pull "
        "requests in the window have a body with an internal-review marker. Markers and method are in "
        "the docstring of `evals/study/check_internal_review.py` and in internal-review-check.json; "
        "they were fixed before the run.", "",
        "Markers: " + "; ".join(f"`{m}` ({d})" for m, d in MARKERS) + ". Recorded, not in the rule: "
        + "; ".join(f"`{m}` ({d})" for m, d in DIAGNOSTIC) + ".", "",
        "| # | repository | v3 | first 12 | PRs in window | with a marker | share | excluded | method | Change-Id: (not in rule) |",
        "|---|---|---|---|---:|---:|---:|---|---|---:|",
    ]
    for i, r in enumerate(rows, 1):
        cid = r["graphql"]["per_marker"]["Change-Id:"] if "graphql" in r else r["diagnostic"]["Change-Id:"]["total_count"]
        lines.append(f"| {i} | {r['repo']} | {'yes' if r['in_v3'] else ''} | {'yes' if r['in_first_12'] else ''} | "
                     f"{r['total']:,} | {r['union']:,} | {r['share']:.1%} | {'**yes**' if r['excluded'] else 'no'} | "
                     f"{r['method']} | {cid:,} |")
    lines += ["", "Per-marker counts (search API; for GraphQL rows, exact counts):", ""]
    for r in rows:
        per = r["graphql"]["per_marker"] if "graphql" in r else {m: v["total_count"] for m, v in r["markers"].items()}
        nz = {m: c for m, c in per.items() if c and m not in dict(DIAGNOSTIC)}
        if nz:
            lines.append(f"- {r['repo']}: " + ", ".join(f"`{m}` {c:,}" for m, c in nz.items())
                         + (f" (search counts: " + ", ".join(f"`{m}` {v['total_count']:,}" for m, v in r["markers"].items()
                                                             if v["total_count"]) + ")" if "graphql" in r else ""))
    if not any("graphql" in r for r in rows):
        lines.append("")
    inc = [r["repo"] for r in rows if r["incomplete_results"]]
    lines += ["", f"Search results flagged incomplete: {', '.join(inc) if inc else 'none'}.",
              f"Excluded: {', '.join(r['repo'] for r in rows if r['excluded']) or 'none'}.", ""]
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG.update(load_log())
    started = now_iso()
    rows = []
    for row in frame():
        rec = check(row)
        rows.append(rec)
        print(f"{rec['repo']}: total {rec['total']} union {rec['union']} share {rec['share']} "
              f"excluded {rec['excluded']} ({rec['method']})", flush=True)
    out = {"generated_at": now_iso(), "started_at": started, "window": [START, END], "threshold": THRESHOLD,
           "verify_at": VERIFY_AT, "markers": [{"marker": m, "why": d} for m, d in MARKERS],
           "diagnostic_markers": [{"marker": m, "why": d} for m, d in DIAGNOSTIC],
           "frame_size": len(rows), "frame_note": "v3 selected (28) together with the first twelve; airflow, "
           "django and rust are in both, so 37", "excluded": [r["repo"] for r in rows if r["excluded"]],
           "repos": rows}
    OUT_JSON.write_text(json.dumps(out, indent=1) + "\n")
    (OUT_DIR / "REPORT.md").write_text(report(rows, started))
    print(f"wrote {OUT_JSON} and {OUT_DIR / 'REPORT.md'}", flush=True)


if __name__ == "__main__":
    main()
