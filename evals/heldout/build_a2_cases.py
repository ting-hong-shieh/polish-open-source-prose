#!/usr/bin/env python3
"""Build the private held-out set A2 from the selected real pull request pairs.

Reads heldout-a2-selected.json and heldout-a2-candidates.json from
$POLISH_EVAL_DATA/Processed/polish-open-source-prose/ and writes heldout-a2-cases.json
there. Each case is the title and description as they stood before the reviewer's
critique; the critique, the author's later text, and the ideal behavior stay with the
case for scoring but are never shown to the model under test.

The cases contain third-party text, so they stay outside Git. evals/heldout/a2_manifest.json
records the URLs and a SHA-256 of the cases file to show the set was fixed before any run.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data")) / "Processed/polish-open-source-prose"


def main() -> None:
    selected = json.loads((DATA / "heldout-a2-selected.json").read_text())
    candidates = {c["url"]: c for c in json.loads((DATA / "heldout-a2-candidates.json").read_text())}
    cases = []
    for s in selected:
        c = candidates[s["url"]]
        owner_repo, number = s["url"].split("github.com/")[1].split("/pull/")
        cases.append({
            "id": f"a2-{owner_repo.split('/')[1]}-{number}",
            "url": s["url"],
            "locale": "en",
            "surface": "pull request title and description",
            "mode": "rewrite",
            "input": f"{c['title_before']}\n\n{(c['body_before'] or '').strip()}",
            "critique_kind": s["critique_kind"],
            "judgeable_from_text": s["judgeable_from_text"],
            "critique_quote": s["critique_quote"],
            "critique_summary": s["critique_summary"],
            "ideal_editor_behavior": s["ideal_editor_behavior"],
            "must_not": s["must_not"],
            "author_after": f"{c['title_after']}\n\n{(c['body_after'] or '').strip()}",
            "must_preserve": [], "must_remove": [], "must_not_introduce": [],
        })
    out = DATA / "heldout-a2-cases.json"
    out.write_text(json.dumps({"version": 1, "cases": cases}, ensure_ascii=False, indent=1) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    manifest = {
        "description": "Private held-out set A2: real pull request titles and descriptions as they stood "
                       "before a reviewer criticized their prose. Text is kept outside Git; this file fixes "
                       "the set by URL and hash before any model ran on it.",
        "cases_file": "$POLISH_EVAL_DATA/Processed/polish-open-source-prose/heldout-a2-cases.json",
        "sha256": digest,
        "cases": [{"id": c["id"], "url": c["url"], "critique_kind": c["critique_kind"],
                   "judgeable_from_text": c["judgeable_from_text"]} for c in cases],
    }
    (Path(__file__).resolve().parent / "a2_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{len(cases)} cases, sha256 {digest}")


if __name__ == "__main__":
    main()
