#!/usr/bin/env python3
"""Pull every comment on pull requests in a fixed window for a fixed list of repositories
(evals/study/CASE_COLLECTION.md, steps 1-3). No filtering, no model calls.

Per repository, writes under $POLISH_EVAL_DATA/Raw/polish-open-source-prose/pr-comments-2026/<owner>__<repo>/:
- pulls.jsonl: one line per pull request created in the window (number, title, body, dates,
  state, author, edit count, review summaries with bodies);
- issue_comments.jsonl: issue-style comments on those pull requests (GraphQL, sized by each
  pull request's comment count);
- review_comments.jsonl: line comments from review threads (GraphQL, sized by thread count);
- counts.json: counts of each.
Raw files hold other people's text and usernames: keep them local.

The repository-wide REST comment listings were tried first and dropped: their `since`
filters by update time, so pages fill with old comments that bots re-edited and the cursor
stalls (apache/airflow stopped at 2026-03-12). GraphQL by pull request has no such problem.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/study/collect_pr_comments.py [--stage pulls|comments|all] [--repos a/b,c/d] [--start 2026-01-01] [--end 2026-09-30]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
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


def gh(*args: str) -> str:
    """Run gh api and return its stdout, which must parse as JSON; truncated or empty output
    (seen once as an "unterminated string" from a 60 MB pull) counts as a transient failure."""
    attempt = 0
    while True:
        p = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
        if p.returncode == 0:
            try:
                json.loads(p.stdout)
                return p.stdout
            except json.JSONDecodeError as exc:
                p.stderr = f"truncated json: {exc}"
        err = p.stderr.lower()
        if "rate limit" in err or "ratelimit" in err:
            # Sleep until the GraphQL window resets, then go on; no retry cap for this case.
            try:
                reset = json.loads(subprocess.run(["gh", "api", "rate_limit"], capture_output=True, text=True).stdout)
                wait = max(30, reset["resources"]["graphql"]["reset"] - int(time.time()) + 15)
            except Exception:
                wait = 600
            print(f"  rate limit: sleeping {wait}s", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        attempt += 1
        if attempt <= 8 and any(k in err for k in ("secondary", "502", "503", "504", "timeout", "unexpected end",
                                                     "connection", "eof", "abuse", "something went wrong",
                                                     "truncated json")):
            wait = 90 * attempt
            print(f"  retry in {wait}s: {p.stderr.strip()[:120]}", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(p.stderr.strip()[:500])


def pull_requests(owner: str, name: str, start: str, end: str, out: Path) -> int:
    """Walk pull requests newest first; keep those created in [start, end]; stop below start.
    Pages are appended as they arrive and the cursor is saved, so a restart resumes."""
    cursor_file = out.with_suffix(".cursor")
    after, n = None, 0
    if cursor_file.exists() and out.exists():
        after = cursor_file.read_text().strip() or None
        n = sum(1 for _ in out.open())
    else:
        out.write_text("")
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
                if day < start:
                    below = True
                    break
                f.write(json.dumps(pr, ensure_ascii=False) + "\n")
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
    return json.loads(gh("graphql", "-f", f"query={q}"))["data"]


def issue_comments(owner: str, name: str, prs: list[dict], out: Path) -> int:
    """Issue-style comments, first:N sized by each PR's comment count; >100 paged singly."""
    todo = [p for p in prs if p["comments"]["totalCount"] > 0]
    n = 0
    with out.open("w") as f:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            parts = [f'p{p["number"]}: repository(owner:"{owner}",name:"{name}"){{ pullRequest(number:{p["number"]}){{ '
                     f'comments(first:{min(p["comments"]["totalCount"], 100)}){{ pageInfo{{ hasNextPage endCursor }} '
                     f'nodes{{ {COMMENT_FIELDS} }} }} }} }}' for p in chunk]
            data = batched_query(parts)
            for p in chunk:
                conn = data[f'p{p["number"]}']["pullRequest"]["comments"]
                nodes = list(conn["nodes"])
                after = conn["pageInfo"]["endCursor"] if conn["pageInfo"]["hasNextPage"] else None
                while after:
                    more = batched_query([f'x: repository(owner:"{owner}",name:"{name}"){{ pullRequest(number:{p["number"]}){{ '
                                          f'comments(first:100, after:"{after}"){{ pageInfo{{ hasNextPage endCursor }} '
                                          f'nodes{{ {COMMENT_FIELDS} }} }} }} }}'])["x"]["pullRequest"]["comments"]
                    nodes += more["nodes"]
                    after = more["pageInfo"]["endCursor"] if more["pageInfo"]["hasNextPage"] else None
                for c in nodes:
                    f.write(json.dumps({"pr_number": p["number"], "html_url": c["url"], "created_at": c["createdAt"],
                                        "body": c["body"], "user": (c["author"] or {}).get("login"),
                                        "author_association": c["authorAssociation"]}, ensure_ascii=False) + "\n")
                    n += 1
    return n


def review_comments(owner: str, name: str, prs: list[dict], out: Path) -> int:
    """Line comments from review threads, first:T threads sized by count, 10 comments per
    thread in the batch; longer threads are completed one by one."""
    todo = [p for p in prs if p["reviewThreads"]["totalCount"] > 0]
    n = 0
    with out.open("w") as f:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            parts = [f'p{p["number"]}: repository(owner:"{owner}",name:"{name}"){{ pullRequest(number:{p["number"]}){{ '
                     f'reviewThreads(first:{min(p["reviewThreads"]["totalCount"], 100)}){{ pageInfo{{ hasNextPage endCursor }} '
                     f'nodes{{ id path comments(first:10){{ totalCount pageInfo{{ hasNextPage endCursor }} nodes{{ {COMMENT_FIELDS} }} }} }} }} }} }}'
                     for p in chunk]
            data = batched_query(parts)
            for p in chunk:
                conn = data[f'p{p["number"]}']["pullRequest"]["reviewThreads"]
                threads = list(conn["nodes"])
                after = conn["pageInfo"]["endCursor"] if conn["pageInfo"]["hasNextPage"] else None
                while after:
                    more = batched_query([f'x: repository(owner:"{owner}",name:"{name}"){{ pullRequest(number:{p["number"]}){{ '
                                          f'reviewThreads(first:100, after:"{after}"){{ pageInfo{{ hasNextPage endCursor }} '
                                          f'nodes{{ id path comments(first:10){{ totalCount pageInfo{{ hasNextPage endCursor }} nodes{{ {COMMENT_FIELDS} }} }} }} }} }} }}'])["x"]["pullRequest"]["reviewThreads"]
                    threads += more["nodes"]
                    after = more["pageInfo"]["endCursor"] if more["pageInfo"]["hasNextPage"] else None
                for t in threads:
                    nodes = list(t["comments"]["nodes"])
                    tafter = t["comments"]["pageInfo"]["endCursor"] if t["comments"]["pageInfo"]["hasNextPage"] else None
                    while tafter:
                        more = batched_query([f'x: node(id:"{t["id"]}"){{ ... on PullRequestReviewThread {{ '
                                              f'comments(first:100, after:"{tafter}"){{ pageInfo{{ hasNextPage endCursor }} nodes{{ {COMMENT_FIELDS} }} }} }} }}'])["x"]["comments"]
                        nodes += more["nodes"]
                        tafter = more["pageInfo"]["endCursor"] if more["pageInfo"]["hasNextPage"] else None
                    for c in nodes:
                        f.write(json.dumps({"pr_number": p["number"], "html_url": c["url"], "created_at": c["createdAt"],
                                            "body": c["body"], "path": t["path"], "user": (c["author"] or {}).get("login"),
                                            "author_association": c["authorAssociation"]}, ensure_ascii=False) + "\n")
                        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", default=",".join(REPOS))
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--stage", default="all", choices=["pulls", "comments", "all"])
    o = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "WINDOW.json").write_text(json.dumps({"start": o.start, "end": o.end, "repos": o.repos.split(","),
                                                 "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1) + "\n")
    for repo in o.repos.split(","):
        owner, name = repo.split("/")
        d = OUT / f"{owner}__{name}"
        d.mkdir(exist_ok=True)
        if o.stage in ("pulls", "all") and not (d / "pulls.done").exists():
            t0 = time.time()
            n = pull_requests(owner, name, o.start, o.end, d / "pulls.jsonl")
            (d / "pulls.done").write_text(f"{n} {round(time.time() - t0)}s\n")
            print(repo, n, "PRs", round(time.time() - t0), "s", flush=True)
        if o.stage in ("comments", "all") and (d / "pulls.done").exists() and not (d / "counts.json").exists():
            t0 = time.time()
            prs = [json.loads(line) for line in (d / "pulls.jsonl").read_text().split("\n") if line]
            counts = {"repo": repo, "window": [o.start, o.end], "pull_requests": len(prs)}
            counts["issue_comments"] = issue_comments(owner, name, prs, d / "issue_comments.jsonl")
            print(repo, counts["issue_comments"], "issue comments", flush=True)
            counts["review_comments"] = review_comments(owner, name, prs, d / "review_comments.jsonl")
            counts["review_summaries_with_body"] = sum(1 for p in prs for r in p["reviews"]["nodes"] if (r["body"] or "").strip())
            counts["reviews_truncated_prs"] = sum(1 for p in prs if p["reviews"]["totalCount"] > 20)
            counts["expected_issue_comments"] = sum(p["comments"]["totalCount"] for p in prs)
            counts["seconds"] = round(time.time() - t0)
            (d / "counts.json").write_text(json.dumps(counts, indent=1) + "\n")
            print(json.dumps(counts), flush=True)


if __name__ == "__main__":
    main()
