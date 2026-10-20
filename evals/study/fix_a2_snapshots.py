#!/usr/bin/env python3
"""Rebuild the A2 inputs that did not match the snapshot at the quoted reviewer comment.

For every case, the input becomes the title and description as they stood just before the
quoted comment (edit history and renames, as in check_a2_snapshots.py). Cases whose input
already matched keep their text byte for byte. Writes a new heldout-a2-cases.json
(version 2) and updates evals/heldout/a2_manifest.json with the new SHA-256, the correction
date, the reason, and the list of corrected cases. The previous case file is kept as
heldout-a2-cases.v1.json.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/study/fix_a2_snapshots.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402
from check_a2_snapshots import THREADS, body_at, title_at  # noqa: E402

MANIFEST = pc.REPO / "evals/heldout/a2_manifest.json"


def main() -> None:
    cases_path = pc.CASES_FILE
    data = json.loads(cases_path.read_bytes())
    feas = {r["url"]: r for r in json.loads((pc.PROC / "a2-commit-feasibility/a2-commit-feasibility.json").read_text())}
    corrected = []
    for case in data["cases"]:
        owner, repo, _, num = case["url"].split("github.com/")[1].split("/")
        pr = json.loads((THREADS / f"{owner}__{repo}__{num}.json").read_text())["pull_request"]
        when = feas[case["url"]]["critique_at"]
        body, _ = body_at(pr, when)
        title, _ = title_at(pr, when)
        new_input = f"{title}\n\n{body.strip()}"
        if pc.normalized(new_input) != pc.normalized(case["input"]):
            corrected.append({"id": case["id"], "comment_at": when,
                              "old_chars": len(case["input"]), "new_chars": len(new_input)})
            case["input"] = new_input
        case["snapshot_at"] = when
    data["version"] = 2
    backup = cases_path.with_name("heldout-a2-cases.v1.json")
    if not backup.exists():
        shutil.copy(cases_path, backup)
    cases_path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    digest = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    manifest = json.loads(MANIFEST.read_text())
    manifest["sha256_v1"] = manifest["sha256"]
    manifest["sha256"] = digest
    manifest["corrected"] = {
        "date": date.today().isoformat(),
        "reason": "The input of each case is the title and description as they stood just before the "
                  "reviewer comment quoted in critique_quote. Version 1 had taken the description before the "
                  "first prose-matching comment in the thread; for four cases the quoted comment came later, "
                  "after the description had been edited, so the editor and judges saw a version the reviewer "
                  "had not. Rounds 2 and 3 ran on version 1. Version 2 corrects those four inputs; the other "
                  "seventeen are unchanged. Each case now records snapshot_at, the comment timestamp.",
        "cases": [c["id"] for c in corrected],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"corrected {len(corrected)} cases; new sha256 {digest}")
    for c in corrected:
        print(f"  {c['id']}: {c['old_chars']} -> {c['new_chars']} chars (comment at {c['comment_at']})")


if __name__ == "__main__":
    main()
