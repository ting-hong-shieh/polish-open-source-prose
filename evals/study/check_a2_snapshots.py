#!/usr/bin/env python3
"""Check that each A2 case's input is the title and description as they stood just before
the reviewer's quoted comment, using the pull request's edit history.

The A2 inputs were built by evals/heldout/extract_real_pairs.py as the body before the
*first* prose-matching critique in the thread; the case's critique_quote was chosen later
and may be a different, later comment. This script recomputes the snapshot at the quoted
comment's timestamp (the comment time from a2-commit-feasibility.json) from the saved
threads' userContentEdits (full body text per edit) and RenamedTitleEvent items, and
compares it with the case input.

Writes a report with the differences (third-party text, outside Git) to
$POLISH_EVAL_DATA/Processed/polish-open-source-prose/a2-snapshot-check/ and prints a
summary without text.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/study/check_a2_snapshots.py
"""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

THREADS = pc.DATA / "Raw/polish-open-source-prose/github-threads"
OUT = pc.PROC / "a2-snapshot-check"


def body_at(pr: dict, when: str) -> tuple[str, str]:
    edits = sorted(pr["userContentEdits"]["nodes"], key=lambda e: e["editedAt"])
    before = [e for e in edits if e["editedAt"] < when and e.get("diff") is not None]
    if before:
        return before[-1]["diff"], f"edit at {before[-1]['editedAt']}"
    if edits and edits[0].get("diff") is not None:
        return edits[0]["diff"], f"first edit {edits[0]['editedAt']} (no edit before the comment)"
    return pr["body"] or "", "current body (no edit history)"


def title_at(pr: dict, when: str) -> tuple[str, str]:
    renames = sorted((r for r in pr["timelineItems"]["nodes"] if r), key=lambda r: r["createdAt"])
    after = [r for r in renames if r["createdAt"] > when]
    if after:
        return after[0]["previousTitle"], f"previousTitle of rename at {after[0]['createdAt']}"
    return pr["title"], "current title (no rename after the comment)"


def main() -> None:
    cases = pc.read_cases()
    feas = {r["url"]: r for r in json.loads((pc.PROC / "a2-commit-feasibility/a2-commit-feasibility.json").read_text())}
    OUT.mkdir(parents=True, exist_ok=True)
    rows, report = [], ["# A2 snapshot check\n", "Case input vs. title/description at the quoted comment's time.\n"]
    for cid, case in cases.items():
        owner, repo, _, num = case["url"].split("github.com/")[1].split("/")
        pr = json.loads((THREADS / f"{owner}__{repo}__{num}.json").read_text())["pull_request"]
        when = feas[case["url"]]["critique_at"]
        body, body_src = body_at(pr, when)
        title, title_src = title_at(pr, when)
        expected = pc.normalized(f"{title}\n\n{body.strip()}")
        actual = pc.normalized(case["input"])
        same = expected == actual
        n_edits = pr["userContentEdits"]["totalCount"]
        edits_before = sum(1 for e in pr["userContentEdits"]["nodes"] if e["editedAt"] < when)
        rows.append((cid, same, when, n_edits, edits_before, body_src, title_src))
        report.append(f"## {cid}\n\n- comment at {when}; {n_edits} body edits, {edits_before} before the comment\n"
                      f"- expected body: {body_src}; expected title: {title_src}\n- match: {same}\n")
        if not same:
            diff = difflib.unified_diff(actual.splitlines(), expected.splitlines(), "case input", "snapshot at comment",
                                        lineterm="", n=1)
            report.append("```diff\n" + "\n".join(diff) + "\n```\n")
    (OUT / "report.md").write_text("\n".join(report))
    (OUT / "summary.json").write_text(json.dumps([dict(zip(("id", "match", "comment_at", "edits", "edits_before",
                                                                 "body_source", "title_source"), r)) for r in rows], indent=1))
    print(f"{sum(r[1] for r in rows)}/{len(rows)} cases match the snapshot at the quoted comment")
    for r in rows:
        print(f"  {'ok  ' if r[1] else 'DIFF'} {r[0]:<24} edits {r[4]}/{r[3]} before comment; body: {r[5]}; title: {r[6]}")


if __name__ == "__main__":
    main()
