#!/usr/bin/env python3
"""Build the round-4 evidence files for the 21 A2 cases (evals/study/PLAN.md, "Cases").

For each case, writes under $POLISH_EVAL_DATA/Processed/polish-open-source-prose/round4-cases/<case-id>/:
- review.md: the earliest comment quoted in the case, verbatim, with reviewer, timestamp, and URL;
- diff.patch: the three-dot diff of the PR head at that time against its base;
- ci.md: check-run names and conclusions for that head commit, plus the combined status.
Also writes round4-cases/index.json (no third-party text) and the reading sheet
round4-cases/FLAGS_SHEET.md for the author's flag.

Inputs: the A2 case file (hash-checked), heldout-a2-selected.json, and a2-commit-feasibility.json
(the head SHA per case). Calls the GitHub API through gh; no model calls.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/study/build_case_files.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
PROC = DATA / "Processed/polish-open-source-prose"
OUT = PROC / "round4-cases"

QUERY = """
query($owner:String!,$repo:String!,$num:Int!){
  repository(owner:$owner,name:$repo){ pullRequest(number:$num){
    title
    comments(first:100){ nodes{ url createdAt body author{login} authorAssociation } }
    reviews(first:50){ nodes{ url submittedAt body state author{login} authorAssociation
      comments(first:50){ nodes{ url createdAt body path author{login} authorAssociation } } } }
  } }
}"""


def gh(*args: str, raw: bool = False):
    for attempt in range(5):
        p = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
        if p.returncode == 0:
            return p.stdout if raw else json.loads(p.stdout)
        if "rate limit" in p.stderr.lower():
            time.sleep(60 * (attempt + 1))
            continue
        raise SystemExit(f"gh api {' '.join(args)}: {p.stderr[:300]}")
    raise SystemExit("rate limited")


def read_a2_cases() -> list[dict]:
    raw = (PROC / "heldout-a2-cases.json").read_bytes()
    expected = json.loads((REPO / "evals/heldout/a2_manifest.json").read_text())["sha256"]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise SystemExit("A2 case file does not match the manifest hash")
    return json.loads(raw)["cases"]


def find_comment(pr: dict, quote: str) -> dict:
    hits = []
    for c in pr["comments"]["nodes"]:
        if quote in (c["body"] or ""):
            hits.append({**c, "kind": "issue comment"})
    for r in pr["reviews"]["nodes"]:
        if quote in (r["body"] or ""):
            hits.append({**r, "createdAt": r["submittedAt"], "kind": f"review ({r['state'].lower()})"})
        for rc in r["comments"]["nodes"]:
            if quote in (rc["body"] or ""):
                hits.append({**rc, "kind": f"review comment on {rc['path']}"})
    if not hits:
        raise SystemExit(f"quote not found: {quote[:60]!r}")
    return min(hits, key=lambda h: h["createdAt"])


def main() -> None:
    cases = read_a2_cases()
    sel = {s["url"]: s for s in json.loads((PROC / "heldout-a2-selected.json").read_text())}
    feas = {r["url"]: r for r in json.loads((PROC / "a2-commit-feasibility/a2-commit-feasibility.json").read_text())}
    OUT.mkdir(parents=True, exist_ok=True)
    index, sheet = [], []
    for case in cases:
        url = case["url"]
        owner, repo, _, num = url.split("github.com/")[1].split("/")
        s, f = sel[url], feas[url]
        sha, base = f["target_sha"], f["base_ref"]
        d = OUT / case["id"]
        d.mkdir(exist_ok=True)
        pr = gh("graphql", "-f", f"query={QUERY}", "-F", f"owner={owner}", "-F", f"repo={repo}", "-F", f"num={num}")
        pr = pr["data"]["repository"]["pullRequest"]
        c = find_comment(pr, s["critique_quote"])
        assert c["createdAt"] == f["critique_at"], (case["id"], c["createdAt"], f["critique_at"])
        (d / "review.md").write_text(
            f"# Review comment\n\nPull request: {url}\nComment: {c['url']}\nKind: {c['kind']}\n"
            f"Reviewer: {c['author']['login']} ({c['authorAssociation'].lower()})\nPosted: {c['createdAt']}\n"
            f"PR head at that time: {sha}\n\n---\n\n{c['body'].strip()}\n")
        diff = gh(f"repos/{owner}/{repo}/compare/{base}...{sha}", "-H", "Accept: application/vnd.github.diff", raw=True)
        (d / "diff.patch").write_text(diff)
        runs = gh("--paginate", f"repos/{owner}/{repo}/commits/{sha}/check-runs?per_page=100", "--jq",
                  ".check_runs[] | {name, conclusion, status, app: .app.slug, started_at}", raw=True)
        runs = [json.loads(line) for line in runs.splitlines() if line.strip()]
        status = gh(f"repos/{owner}/{repo}/commits/{sha}/status")
        counts: dict[str, int] = {}
        for r in runs:
            k = r["conclusion"] or r["status"]
            counts[k] = counts.get(k, 0) + 1
        lines = [f"# CI for commit {sha}", "", f"Pull request: {url}", f"Check runs: {len(runs)} "
                 f"({', '.join(f'{k} {v}' for k, v in sorted(counts.items()))})",
                 f"Combined commit status: {status['state']} ({status['total_count']} contexts)", "",
                 "| Check | Conclusion |", "|---|---|"]
        for r in sorted(runs, key=lambda r: ((r["conclusion"] or r["status"]) == "success", r["name"])):
            lines.append(f"| {r['name']} | {r['conclusion'] or r['status']} |")
        for ctx in status.get("statuses", []):
            lines.append(f"| {ctx['context']} (status) | {ctx['state']} |")
        (d / "ci.md").write_text("\n".join(lines) + "\n")
        diff_lines = diff.count("\n")
        entry = {"id": case["id"], "url": url, "head_sha": sha, "base_ref": base, "critique_kind": s["critique_kind"],
                 "judgeable_from_text": s["judgeable_from_text"], "comment_url": c["url"], "comment_kind": c["kind"],
                 "comment_at": c["createdAt"], "diff_files": f["pr_diff_files"], "diff_lines": diff_lines,
                 "diff_additions": f["pr_diff_additions"], "diff_deletions": f["pr_diff_deletions"],
                 "check_runs": len(runs), "check_conclusions": counts, "combined_status": status["state"]}
        index.append(entry)
        sheet.append(
            f"## {case['id']}\n\n- PR: {url}\n- Comment: {c['url']} ({c['kind']}, {c['author']['login']}, "
            f"{c['createdAt']})\n- Drafted kind: {s['critique_kind']}; drafted text-only flag: {s['judgeable_from_text']}\n"
            f"- Diff: {f['pr_diff_files']} files, +{f['pr_diff_additions']} / -{f['pr_diff_deletions']} "
            f"({diff_lines} patch lines); CI: {', '.join(f'{k} {v}' for k, v in sorted(counts.items()))}\n\n"
            f"> {c['body'].strip().replace(chr(10), chr(10) + '> ')}\n\n"
            f"**Flag** (criticizes the description or title, and diff + CI are enough to act on it): [ ] yes  [ ] no\n\n"
            f"Note: \n")
        print(case["id"], c["kind"], f"{f['pr_diff_files']} files", f"{diff_lines} lines", f"{len(runs)} runs", flush=True)
    (OUT / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    (OUT / "FLAGS_SHEET.md").write_text(
        "# Round 4 flag sheet (21 A2 cases)\n\nFor each case, read the comment and tick one flag: does it criticize "
        "the description or title (not only the code), and are the diff and CI enough to act on it? "
        "Third-party text; stays outside Git. The flags go into evals/study/flags.json.\n\n" + "\n".join(sheet))


if __name__ == "__main__":
    main()
