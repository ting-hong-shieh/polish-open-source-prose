#!/usr/bin/env python3
"""Pull every comment on pull requests in a fixed window for a list of repositories
(evals/study/CASE_COLLECTION.md, steps 1-3). No filtering, no model calls.

Per job (one repository and one window), writes under
$POLISH_EVAL_DATA/Raw/polish-open-source-prose/pr-comments-2026/<owner>__<repo>/ (or, for a
job with a segment, its sub-run directory <owner>__<repo>/<segment>/):
- pulls.jsonl: one line per pull request created in the window (number, title, body, dates,
  state, author, edit count, review summaries with bodies);
- issue_comments.jsonl: issue-style comments on those pull requests (GraphQL, sized by each
  pull request's comment count);
- review_comments.jsonl: line comments from review threads (GraphQL, sized by thread count);
- counts.json: counts of each, the window, and the start and end time of each stage;
- job.json: the job (repository, window, segment, plan) written when it starts; a rerun with
  a different window for the same directory stops instead of mixing windows.
Raw files hold other people's text and usernames: keep them local.

The repository-wide REST comment listings were tried first and dropped: their `since`
filters by update time, so pages fill with old comments that bots re-edited and the cursor
stalls (apache/airflow stopped at 2026-03-12). GraphQL by pull request has no such problem.

Jobs come from a plan (--plan, JSON: {"name": ..., "jobs": [{"repo", "start", "end",
"segment"}]}, run in the listed order) or from --repos / --repos-file with --start/--end
(and optionally --segment). Every job is resumable:
- pull requests: the newest-first walk first skips, with a light query (createdAt only), the
  pull requests created after the window, then walks the window with the full query; the
  cursor is saved after every page and rows already written are not written again;
- comments: the batch index and the byte length of the output are saved after every batch;
  a restart truncates to that length and continues with the next batch.
A pull request deleted between the two stages (GraphQL NOT_FOUND) is recorded in counts.json
as missing instead of stopping the run. A job that fails is logged and the run goes on to
the next job; rerunning the same command resumes it. Primary rate limits sleep until the
GraphQL window resets; secondary limits sleep 3 minutes.

Each job's start, end and counts go to stdout (collect.log under nohup) and, one JSON line
per event, to runs/<plan name>.jsonl. Before a plan run changes WINDOW.json, the previous
one is kept as WINDOW.<start>_<end>.json.

Extending a repository whose window was pulled earlier: give the job the earlier part as a
segment (for example 2025-10-01_2025-12-31). The segment is written to its own sub-run
directory and the earlier files are not touched. `--stage merge` then appends each finished
segment to the repository's top-level files: the old files stay a byte-identical prefix
(their size and SHA-256 are recorded in MERGE-<segment>.json and checked before the new
file replaces the old one), segment rows whose pull request number is already present are
skipped, counts.json is first copied to counts.<old start>_<old end>.json, and the
sub-run directory is kept.

Usage:
  POLISH_EVAL_DATA=/mnt/d/Data python3 -I evals/study/collect_pr_comments.py --plan PLAN.json
  POLISH_EVAL_DATA=/mnt/d/Data python3 -I evals/study/collect_pr_comments.py --plan PLAN.json --stage merge
  POLISH_EVAL_DATA=/mnt/d/Data python3 -I evals/study/collect_pr_comments.py --repos a/b --start 2026-01-01 --end 2026-09-30
Options: --stage pulls|comments|all|merge, --out DIR (another output root, for tests),
--max-prs N (stop each job after N pull requests; tests only).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
OUT = DATA / "Raw/polish-open-source-prose/pr-comments-2026"

# Chosen before reading any comment (CASE_COLLECTION.md step 1). The four repositories already
# used, plus eight large active projects across languages and ecosystems. Four candidates from
# the spec (pytorch/pytorch, home-assistant/core, grafana/grafana, elastic/elasticsearch) were
# left out for volume alone: each had 14,000-22,000 pull requests in the window, together more
# than the twelve kept; they can be added later as a separate pull. golang/go was in the first
# list and dropped after one test pull showed that its pull requests are mirrored to Gerrit and
# carry only bot comments on GitHub; prometheus/prometheus (Go) took its place.
# Pulled for 2026-01-01..2026-09-30 on 2026-10-20/21; the default when no plan is given.
REPOS = ["apache/airflow", "apache/datafusion", "apache/arrow", "python/cpython",
         "kubernetes/kubernetes", "rust-lang/rust", "pandas-dev/pandas", "numpy/numpy",
         "nodejs/node", "prometheus/prometheus", "apache/spark", "django/django"]

PR_QUERY = """
query($owner:String!,$name:String!,$after:String){
  repository(owner:$owner,name:$name){
    pullRequests(first:100, orderBy:{field:CREATED_AT, direction:DESC}, after:$after){
      pageInfo{ hasNextPage endCursor }
      nodes{ number title body createdAt closedAt mergedAt state isDraft url
        author{ login } authorAssociation
        userContentEdits(first:1){ totalCount }
        reviews(first:20){ totalCount nodes{ id submittedAt state body author{ login } authorAssociation comments(first:1){ totalCount } } }
        comments(first:1){ totalCount }
        reviewThreads(first:1){ totalCount }
      }
    }
  }
}"""

# Same connection and order as PR_QUERY, creation dates only: used to skip the pull requests
# created after the window at about 1 point per page instead of about 24.
SEEK_QUERY = """
query($owner:String!,$name:String!,$after:String){
  repository(owner:$owner,name:$name){
    pullRequests(first:100, orderBy:{field:CREATED_AT, direction:DESC}, after:$after){
      pageInfo{ hasNextPage endCursor }
      nodes{ createdAt }
    }
  }
}"""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def log(msg: str) -> None:
    print(f"[{now_iso()}] {msg}", flush=True)


def gh(*args: str, allow_not_found: bool = False) -> str:
    """Run gh api and return its stdout, which must parse as JSON; truncated or empty output
    (seen once as an "unterminated string" from a 60 MB pull) counts as a transient failure.
    With allow_not_found, a GraphQL answer whose only errors are NOT_FOUND (a pull request
    deleted since it was listed) is returned with its partial data."""
    attempt = 0
    while True:
        p = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
        if p.returncode == 0:
            try:
                json.loads(p.stdout)
                return p.stdout
            except json.JSONDecodeError as exc:
                p.stderr = f"truncated json: {exc}"
        elif allow_not_found:
            try:
                body = json.loads(p.stdout)
                if body.get("data") is not None and body.get("errors") and \
                        all(e.get("type") == "NOT_FOUND" for e in body["errors"]):
                    return p.stdout
            except (json.JSONDecodeError, AttributeError):
                pass
        err = p.stderr.lower()
        if "secondary rate limit" in err or "abuse" in err:
            print("  secondary rate limit: sleeping 180s", file=sys.stderr, flush=True)
            time.sleep(180)
            continue
        if "rate limit" in err or "ratelimit" in err or "rate_limited" in err:
            # Sleep until the GraphQL window resets, then go on; no retry cap for this case.
            try:
                lim = json.loads(subprocess.run(["gh", "api", "rate_limit"], capture_output=True, text=True).stdout)
                g = lim["resources"]["graphql"]
                wait = max(30, g["reset"] - int(time.time()) + 15) if g["remaining"] < 50 else 60
            except Exception:
                wait = 600
            print(f"  rate limit: sleeping {wait}s", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        attempt += 1
        if attempt <= 8 and any(k in err for k in ("502", "503", "504", "timeout", "unexpected end",
                                                     "connection", "eof", "something went wrong",
                                                     "truncated json", "tls", "reset by peer")):
            wait = 90 * attempt
            print(f"  retry in {wait}s: {p.stderr.strip()[:120]}", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(p.stderr.strip()[:500])


def seek(owner: str, name: str, end: str) -> str | None:
    """Cursor from which the newest-first walk reaches pull requests created on or before
    `end` (None: from the top). Pages wholly after the window are skipped with SEEK_QUERY."""
    after = None
    while True:
        args = ["graphql", "-f", f"query={SEEK_QUERY}", "-F", f"owner={owner}", "-F", f"name={name}"]
        if after:
            args += ["-F", f"after={after}"]
        page = json.loads(gh(*args))["data"]["repository"]["pullRequests"]
        nodes = page["nodes"]
        if not nodes or nodes[-1]["createdAt"][:10] <= end or not page["pageInfo"]["hasNextPage"]:
            return after
        after = page["pageInfo"]["endCursor"]


def pull_requests(owner: str, name: str, start: str, end: str, out: Path, max_prs: int | None = None) -> int:
    """Walk pull requests newest first; keep those created in [start, end]; stop below start.
    Pages are appended as they arrive and the cursor is saved, so a restart resumes; a
    pull request already in the file is not written twice."""
    cursor_file = out.with_suffix(".cursor")
    seen: set[int] = set()
    if cursor_file.exists() and out.exists():
        after = cursor_file.read_text().strip() or None
        seen = {json.loads(line)["number"] for line in out.read_text().split("\n") if line}
        log(f"{owner}/{name}: resuming pull requests at {len(seen)}")
    else:
        out.write_text("")
        after = seek(owner, name, end)
        cursor_file.write_text(after or "")
    n = len(seen)
    with out.open("a") as f:
        while True:
            args = ["graphql", "-f", f"query={PR_QUERY}", "-F", f"owner={owner}", "-F", f"name={name}"]
            if after:
                args += ["-F", f"after={after}"]
            page = json.loads(gh(*args))["data"]["repository"]["pullRequests"]
            below = False
            for pr in page["nodes"]:
                day = pr["createdAt"][:10]
                if day > end:
                    continue
                if day < start or (max_prs is not None and n >= max_prs):
                    below = True
                    break
                if pr["number"] in seen:
                    continue
                f.write(json.dumps(pr, ensure_ascii=False) + "\n")
                seen.add(pr["number"])
                n += 1
            f.flush()
            if below or not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
            cursor_file.write_text(after)
    cursor_file.unlink(missing_ok=True)
    return n


COMMENT_FIELDS = "url createdAt body author{ login } authorAssociation"
BATCH = 25


def batched_query(parts: list[str]) -> dict:
    q = "query{ " + " ".join(parts) + " }"
    return json.loads(gh("graphql", "-f", f"query={q}", allow_not_found=True))["data"]


def resumable(out: Path, prs: list[dict], fetch_chunk, missing: list[int]) -> int:
    """Run fetch_chunk over the pull requests in batches of BATCH, appending its rows to `out`.
    After each batch the next batch index, the byte length and the row count go to
    <out>.progress; a restart truncates `out` to that length and continues. On completion
    <out>.done holds the row count and the pull requests found missing."""
    prog, done = out.with_suffix(".progress"), out.with_suffix(".done")
    if done.exists():
        d = json.loads(done.read_text())
        missing.extend(d["missing"])
        return d["rows"]
    first, n = 0, 0
    if prog.exists() and out.exists():
        p = json.loads(prog.read_text())
        first, n = p["next_batch"], p["rows"]
        missing.extend(p.get("missing", []))
        with out.open("r+b") as f:
            f.truncate(p["bytes"])
        log(f"  resuming {out.name} at batch {first} ({n} rows)")
    else:
        out.write_bytes(b"")
    with out.open("ab") as f:
        for b, i in enumerate(range(0, len(prs), BATCH)):
            if b < first:
                continue
            for row in fetch_chunk(prs[i:i + BATCH], missing):
                f.write((json.dumps(row, ensure_ascii=False) + "\n").encode())
                n += 1
            f.flush()
            tmp = prog.with_suffix(".progress.tmp")
            tmp.write_text(json.dumps({"next_batch": b + 1, "bytes": f.tell(), "rows": n, "missing": sorted(set(missing))}))
            os.replace(tmp, prog)
    done.write_text(json.dumps({"rows": n, "missing": sorted(set(missing))}) + "\n")
    prog.unlink(missing_ok=True)
    return n


def issue_comments(owner: str, name: str, prs: list[dict], out: Path, missing: list[int]) -> int:
    """Issue-style comments, first:N sized by each PR's comment count; >100 paged singly."""
    todo = [p for p in prs if p["comments"]["totalCount"] > 0]

    def chunk_rows(chunk: list[dict], missing: list[int]):
        parts = [f'p{p["number"]}: repository(owner:"{owner}",name:"{name}"){{ pullRequest(number:{p["number"]}){{ '
                 f'comments(first:{min(p["comments"]["totalCount"], 100)}){{ pageInfo{{ hasNextPage endCursor }} '
                 f'nodes{{ {COMMENT_FIELDS} }} }} }} }}' for p in chunk]
        data = batched_query(parts)
        for p in chunk:
            pr = (data.get(f'p{p["number"]}') or {}).get("pullRequest")
            if pr is None:
                missing.append(p["number"])
                continue
            conn = pr["comments"]
            nodes = list(conn["nodes"])
            after = conn["pageInfo"]["endCursor"] if conn["pageInfo"]["hasNextPage"] else None
            while after:
                more = (batched_query([f'x: repository(owner:"{owner}",name:"{name}"){{ pullRequest(number:{p["number"]}){{ '
                                       f'comments(first:100, after:"{after}"){{ pageInfo{{ hasNextPage endCursor }} '
                                       f'nodes{{ {COMMENT_FIELDS} }} }} }} }}'])["x"].get("pullRequest") or {}).get("comments")
                if more is None:
                    break
                nodes += more["nodes"]
                after = more["pageInfo"]["endCursor"] if more["pageInfo"]["hasNextPage"] else None
            for c in nodes:
                yield {"pr_number": p["number"], "html_url": c["url"], "created_at": c["createdAt"],
                       "body": c["body"], "user": (c["author"] or {}).get("login"),
                       "author_association": c["authorAssociation"]}

    return resumable(out, todo, chunk_rows, missing)


def review_comments(owner: str, name: str, prs: list[dict], out: Path, missing: list[int]) -> int:
    """Line comments from review threads, first:T threads sized by count, 10 comments per
    thread in the batch; longer threads are completed one by one."""
    todo = [p for p in prs if p["reviewThreads"]["totalCount"] > 0]
    tsel = f'nodes{{ id path comments(first:10){{ totalCount pageInfo{{ hasNextPage endCursor }} nodes{{ {COMMENT_FIELDS} }} }} }}'

    def chunk_rows(chunk: list[dict], missing: list[int]):
        parts = [f'p{p["number"]}: repository(owner:"{owner}",name:"{name}"){{ pullRequest(number:{p["number"]}){{ '
                 f'reviewThreads(first:{min(p["reviewThreads"]["totalCount"], 100)}){{ pageInfo{{ hasNextPage endCursor }} '
                 f'{tsel} }} }} }}' for p in chunk]
        data = batched_query(parts)
        for p in chunk:
            pr = (data.get(f'p{p["number"]}') or {}).get("pullRequest")
            if pr is None:
                missing.append(p["number"])
                continue
            conn = pr["reviewThreads"]
            threads = list(conn["nodes"])
            after = conn["pageInfo"]["endCursor"] if conn["pageInfo"]["hasNextPage"] else None
            while after:
                more = (batched_query([f'x: repository(owner:"{owner}",name:"{name}"){{ pullRequest(number:{p["number"]}){{ '
                                       f'reviewThreads(first:100, after:"{after}"){{ pageInfo{{ hasNextPage endCursor }} '
                                       f'{tsel} }} }} }}'])["x"].get("pullRequest") or {}).get("reviewThreads")
                if more is None:
                    break
                threads += more["nodes"]
                after = more["pageInfo"]["endCursor"] if more["pageInfo"]["hasNextPage"] else None
            for t in threads:
                nodes = list(t["comments"]["nodes"])
                tafter = t["comments"]["pageInfo"]["endCursor"] if t["comments"]["pageInfo"]["hasNextPage"] else None
                while tafter:
                    more = (batched_query([f'x: node(id:"{t["id"]}"){{ ... on PullRequestReviewThread {{ '
                                           f'comments(first:100, after:"{tafter}"){{ pageInfo{{ hasNextPage endCursor }} '
                                           f'nodes{{ {COMMENT_FIELDS} }} }} }} }}']).get("x") or {}).get("comments")
                    if more is None:
                        break
                    nodes += more["nodes"]
                    tafter = more["pageInfo"]["endCursor"] if more["pageInfo"]["hasNextPage"] else None
                for c in nodes:
                    yield {"pr_number": p["number"], "html_url": c["url"], "created_at": c["createdAt"],
                           "body": c["body"], "path": t["path"], "user": (c["author"] or {}).get("login"),
                           "author_association": c["authorAssociation"]}

    return resumable(out, todo, chunk_rows, missing)


# ----------------------------------------------------------------------------- jobs

def job_dir(root: Path, job: dict) -> Path:
    owner, name = job["repo"].split("/")
    d = root / f"{owner}__{name}"
    return d / job["segment"] if job.get("segment") else d


def event(run_log: Path | None, **kw) -> None:
    if run_log is None:
        return
    with run_log.open("a") as f:
        f.write(json.dumps({"at": now_iso(), **kw}) + "\n")


def run_job(root: Path, job: dict, stage: str, plan_name: str, run_log: Path | None, max_prs: int | None) -> None:
    repo, start, end = job["repo"], job["start"], job["end"]
    owner, name = repo.split("/")
    d = job_dir(root, job)
    d.mkdir(parents=True, exist_ok=True)
    # Never mix windows in one directory.
    jf = d / "job.json"
    if (d / "counts.json").exists():  # finished (or merged): its window is the one that counts
        c = json.loads((d / "counts.json").read_text())
        if [start, end] not in [c.get("window")] + [s.get("window") for s in c.get("segments", [])]:
            raise RuntimeError(f"{d} holds {c.get('window')}, job asks {start}..{end}; give the job a segment")
    elif jf.exists():
        prev = json.loads(jf.read_text())
        if [prev["start"], prev["end"]] != [start, end]:
            raise RuntimeError(f"{d} holds {prev['start']}..{prev['end']}, job asks {start}..{end}")
    else:
        jf.write_text(json.dumps({"repo": repo, "start": start, "end": end, "segment": job.get("segment"),
                                  "plan": plan_name, "created_at": now_iso(), "max_prs": max_prs}, indent=1) + "\n")
    label = f"{repo}" + (f" [{job['segment']}]" if job.get("segment") else "") + f" {start}..{end}"
    if (d / "counts.json").exists():
        log(f"{label}: done earlier, skipped")
        event(run_log, event="skip", repo=repo, segment=job.get("segment"), reason="counts.json exists")
        return
    times = json.loads((d / "times.json").read_text()) if (d / "times.json").exists() else {}

    def save_times() -> None:
        (d / "times.json").write_text(json.dumps(times, indent=1) + "\n")

    if stage in ("pulls", "all") and not (d / "pulls.done").exists():
        times.setdefault("pulls_started_at", now_iso())
        save_times()
        log(f"{label}: pull requests...")
        event(run_log, event="pulls_start", repo=repo, segment=job.get("segment"), start=start, end=end)
        t0 = time.time()
        n = pull_requests(owner, name, start, end, d / "pulls.jsonl", max_prs)
        secs = round(time.time() - t0)
        (d / "pulls.done").write_text(f"{n} {secs}s\n")
        times["pulls_finished_at"] = now_iso()
        times["pulls_seconds"] = times.get("pulls_seconds", 0) + secs
        save_times()
        log(f"{label}: {n} PRs in {secs}s")
        event(run_log, event="pulls_done", repo=repo, segment=job.get("segment"), pull_requests=n, seconds=secs)
    if stage in ("comments", "all") and (d / "pulls.done").exists():
        times.setdefault("comments_started_at", now_iso())
        save_times()
        t0 = time.time()
        prs = [json.loads(line) for line in (d / "pulls.jsonl").read_text().split("\n") if line]
        missing: list[int] = []
        counts = {"repo": repo, "window": [start, end], "segment": job.get("segment"), "plan": plan_name,
                  "pull_requests": len(prs)}
        counts["issue_comments"] = issue_comments(owner, name, prs, d / "issue_comments.jsonl", missing)
        log(f"{label}: {counts['issue_comments']} issue comments")
        counts["review_comments"] = review_comments(owner, name, prs, d / "review_comments.jsonl", missing)
        counts["review_summaries_with_body"] = sum(1 for p in prs for r in p["reviews"]["nodes"] if (r["body"] or "").strip())
        counts["reviews_truncated_prs"] = sum(1 for p in prs if p["reviews"]["totalCount"] > 20)
        counts["expected_issue_comments"] = sum(p["comments"]["totalCount"] for p in prs)
        counts["missing_prs"] = sorted(set(missing))
        if max_prs is not None:
            counts["max_prs"] = max_prs
        secs = round(time.time() - t0)
        times["comments_finished_at"] = now_iso()
        times["comments_seconds"] = times.get("comments_seconds", 0) + secs
        counts["seconds"] = times["comments_seconds"]
        counts.update(times)
        save_times()
        (d / "counts.json").write_text(json.dumps(counts, indent=1) + "\n")
        log(json.dumps(counts))
        event(run_log, event="comments_done", repo=repo, segment=job.get("segment"),
              **{k: v for k, v in counts.items() if k not in ("repo", "segment", "missing_prs")},
              missing_prs=len(counts["missing_prs"]))


# ----------------------------------------------------------------------------- merge

def sha256(path: Path, limit: int | None = None) -> str:
    h, left = hashlib.sha256(), limit
    with path.open("rb") as f:
        while True:
            buf = f.read(1 << 20 if left is None else min(1 << 20, left))
            if not buf:
                break
            h.update(buf)
            if left is not None:
                left -= len(buf)
                if left <= 0:
                    break
    return h.hexdigest()


def merge_segment(root: Path, job: dict) -> None:
    """Append a finished segment to the repository's top-level files (see the module docstring)."""
    seg = job_dir(root, job)
    top = seg.parent
    manifest = top / f"MERGE-{job['segment']}.json"
    if manifest.exists():
        log(f"{job['repo']} [{job['segment']}]: merged earlier, skipped")
        return
    if not (seg / "counts.json").exists() or not (top / "counts.json").exists():
        log(f"{job['repo']} [{job['segment']}]: segment or top level not finished, not merged")
        return
    old = json.loads((top / "counts.json").read_text())
    new = json.loads((seg / "counts.json").read_text())
    if new.get("max_prs") is not None:
        raise RuntimeError(f"{seg} was a capped test pull (--max-prs), not merged")
    day = dt.date.fromisoformat(new["window"][1]) + dt.timedelta(days=1)
    if day.isoformat() != old["window"][0]:
        raise RuntimeError(f"{seg} ({new['window']}) does not end the day before {top} starts ({old['window']})")
    have = {json.loads(line)["number"] for line in (top / "pulls.jsonl").read_text().split("\n") if line}
    files = {}
    for fname, key in (("pulls.jsonl", "number"), ("issue_comments.jsonl", "pr_number"), ("review_comments.jsonl", "pr_number")):
        src, dst = seg / fname, top / fname
        size, digest = dst.stat().st_size, sha256(dst)
        tmp = dst.with_suffix(".jsonl.merging")
        shutil.copyfile(dst, tmp)
        added = skipped = 0
        with tmp.open("ab") as out:
            for line in src.read_bytes().split(b"\n"):
                if not line:
                    continue
                if json.loads(line)[key] in have:
                    skipped += 1
                    continue
                out.write(line + b"\n")
                added += 1
        if sha256(tmp, size) != digest:
            tmp.unlink()
            raise RuntimeError(f"prefix check failed for {dst}")
        os.replace(tmp, dst)
        files[fname] = {"old_bytes": size, "old_sha256": digest, "rows_added": added, "rows_skipped_duplicate": skipped,
                        "new_bytes": dst.stat().st_size, "new_sha256": sha256(dst)}
    backup = top / f"counts.{old['window'][0]}_{old['window'][1]}.json"
    if not backup.exists():
        shutil.copyfile(top / "counts.json", backup)
    merged = {"repo": job["repo"], "window": [min(old["window"][0], new["window"][0]), max(old["window"][1], new["window"][1])],
              "pull_requests": old["pull_requests"] + files["pulls.jsonl"]["rows_added"],
              "issue_comments": old["issue_comments"] + files["issue_comments.jsonl"]["rows_added"],
              "review_comments": old["review_comments"] + files["review_comments.jsonl"]["rows_added"],
              "merged_at": now_iso(), "segments": [old, new]}
    for k in ("review_summaries_with_body", "reviews_truncated_prs", "expected_issue_comments"):
        merged[k] = old.get(k, 0) + new.get(k, 0)
    (top / "counts.json").write_text(json.dumps(merged, indent=1) + "\n")
    manifest.write_text(json.dumps({"repo": job["repo"], "segment": job["segment"], "merged_at": merged["merged_at"],
                                    "counts_backup": backup.name, "files": files}, indent=1) + "\n")
    log(f"{job['repo']} [{job['segment']}]: merged, {files['pulls.jsonl']['rows_added']} PRs added")


# ----------------------------------------------------------------------------- main

def load_jobs(o: argparse.Namespace) -> tuple[str, list[dict]]:
    if o.plan:
        plan = json.loads(Path(o.plan).read_text())
        return plan["name"], plan["jobs"]
    if o.repos_file:
        text = Path(o.repos_file).read_text()
        repos = json.loads(text) if text.lstrip().startswith("[") else [l.strip() for l in text.splitlines() if l.strip()]
    else:
        repos = o.repos.split(",")
    return f"adhoc-{o.start}_{o.end}", [{"repo": r, "start": o.start, "end": o.end, "segment": o.segment} for r in repos]


def write_window(root: Path, name: str, jobs: list[dict]) -> None:
    w = root / "WINDOW.json"
    if w.exists():
        prev = json.loads(w.read_text())
        if prev.get("plan") == name:
            return
        if "start" in prev:
            backup = root / f"WINDOW.{prev['start']}_{prev['end']}.json"
        else:
            backup = root / f"WINDOW.{prev.get('plan', 'previous')}.json"
        if not backup.exists():
            shutil.copyfile(w, backup)
    w.write_text(json.dumps({"plan": name, "started_at": now_iso(),
                             "jobs": [{k: j.get(k) for k in ("repo", "start", "end", "segment")} for j in jobs]},
                            indent=1) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", help="JSON plan: {name, jobs: [{repo, start, end, segment}]}, run in order")
    ap.add_argument("--repos", default=",".join(REPOS))
    ap.add_argument("--repos-file", help="one owner/name per line, or a JSON list")
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--segment", help="write to <owner>__<repo>/<segment>/ instead of the top level")
    ap.add_argument("--stage", default="all", choices=["pulls", "comments", "all", "merge"])
    ap.add_argument("--out", type=Path, default=OUT, help="output root (default: the raw data directory)")
    ap.add_argument("--max-prs", type=int, help="stop each job after this many pull requests (tests only)")
    o = ap.parse_args()
    root = o.out
    root.mkdir(parents=True, exist_ok=True)
    name, jobs = load_jobs(o)
    if o.stage == "merge":
        for job in jobs:
            if job.get("segment"):
                merge_segment(root, job)
        return
    write_window(root, name, jobs)
    (root / "runs").mkdir(exist_ok=True)
    run_log = root / "runs" / f"{name}.jsonl"
    event(run_log, event="run_start", plan=name, stage=o.stage, jobs=len(jobs), pid=os.getpid())
    log(f"run {name}: {len(jobs)} jobs, stage {o.stage}")
    failed = []
    for job in jobs:
        try:
            run_job(root, job, o.stage, name, run_log, o.max_prs)
        except Exception as exc:  # log, go on; a rerun resumes this job
            failed.append(job["repo"])
            log(f"{job['repo']}: FAILED: {exc}")
            traceback.print_exc(file=sys.stdout)
            event(run_log, event="failed", repo=job["repo"], segment=job.get("segment"), error=str(exc)[:500])
    event(run_log, event="run_end", plan=name, failed=failed)
    log(f"run {name} finished; failed: {', '.join(failed) or 'none'}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
