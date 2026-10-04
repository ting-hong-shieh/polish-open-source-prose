#!/usr/bin/env python3
"""Find real before/after pairs for the private held-out set (A2).

A candidate is a pull request where someone other than the author criticized the
description, title, or wording, and the author then changed the description or title.
For each candidate this writes the text before the first such critique, the critique
comments, and the text after it, to
$POLISH_EVAL_DATA/Processed/polish-open-source-prose/heldout-a2-candidates.json.

The output contains third-party text: keep it local; publish only counts and links.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
THREADS = DATA / "Raw/polish-open-source-prose/github-threads"
OUT = DATA / "Processed/polish-open-source-prose/heldout-a2-candidates.json"

PROSE = re.compile(r"\b(description|descriptions|pr body|pr title|title|summary|wording|reword|"
                   r"own words|explain|explanation|concise|verbose|too long|misleading|"
                   r"does(?:n't| not) match|not accurate|inaccurate|overclaim|ai[- ]generated|llm)\b", re.I)


def login(node: dict) -> str:
    return ((node or {}).get("author") or {}).get("login") or ""


def comments(pr: dict) -> list[dict]:
    items = list(pr["comments"]["nodes"])
    for review in pr["reviews"]["nodes"]:
        items.append({**review, "createdAt": review.get("submittedAt")})
        items.extend(review["comments"]["nodes"])
    return sorted((c for c in items if c.get("body") and c.get("createdAt")), key=lambda c: c["createdAt"])


def body_at(pr: dict, when: str) -> str:
    """Body text as it stood just before `when`.

    GitHub documents UserContentEdit.diff as a summary of the edit, but for pull request bodies
    it holds the full text: in the collected threads the newest edit's diff equals the current
    body in 302 of 303 pull requests (the exception had its body cleared afterwards).
    """
    edits = sorted(pr["userContentEdits"]["nodes"], key=lambda e: e["editedAt"])
    before = [e for e in edits if e["editedAt"] < when and e.get("diff") is not None]
    if before:
        return before[-1]["diff"]
    return edits[0]["diff"] if edits and edits[0].get("diff") is not None else pr["body"]


def main() -> None:
    out = []
    for f in sorted(THREADS.glob("*__*.json")):  # skip MANIFEST.json
        pr = json.loads(f.read_text())["pull_request"]
        author = login(pr)
        critiques = [c for c in comments(pr)
                     if login(c) not in (author, "") and "bot" not in login(c).lower()
                     and PROSE.search(c["body"])]
        if not critiques:
            continue
        first = critiques[0]["createdAt"]
        body_before = body_at(pr, first)
        body_after = pr["body"] or ""
        renames = [r for r in pr["timelineItems"]["nodes"] if r and r["createdAt"] > first]
        title_before = renames[0]["previousTitle"] if renames else pr["title"]
        changed_body = (body_before or "").strip() != body_after.strip()
        if not (changed_body or renames):
            continue
        out.append({
            "url": pr["url"], "state": pr["state"], "merged": pr["merged"],
            "title_before": title_before, "title_after": pr["title"],
            "body_before": body_before, "body_after": body_after,
            "critiques": [{"at": c["createdAt"], "association": c.get("authorAssociation"),
                           "body": c["body"]} for c in critiques[:4]],
            "body_words_before": len((body_before or "").split()),
            "body_words_after": len(body_after.split()),
        })
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{len(out)} candidates -> {OUT}")


if __name__ == "__main__":
    main()
