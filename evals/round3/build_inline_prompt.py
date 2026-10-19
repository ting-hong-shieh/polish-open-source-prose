#!/usr/bin/env python3
"""Build the skill_inline prefix: the v0.2.0 skill text pasted into the prompt.

The prefix is the body of SKILL.md at tag v0.2.0 (frontmatter removed, since that is
discovery metadata the agent uses to decide whether to load the skill), followed by the
two reference files verbatim, each under a heading that repeats the path SKILL.md links
to. Nothing else is added, so the only difference from the v0.2.0 condition is how the
same words reach the model: in the prompt instead of through the skill mechanism.

Writes evals/prompts/skill-inline-v0.2.0.txt and prints its SHA-256, which
evals/round3/PLAN.md records.

Usage: python3 evals/round3/build_inline_prompt.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TAG = "v0.2.0"
SKILL = "skills/polish-open-source-prose"
REFS = ["references/locales/zh-Hant-TW.md", "references/provenance.md"]
OUT = REPO / "evals/prompts/skill-inline-v0.2.0.txt"


def show(path: str) -> str:
    return subprocess.check_output(["git", "show", f"{TAG}:{SKILL}/{path}"], cwd=REPO, text=True)


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        raise SystemExit("SKILL.md has no frontmatter; refusing to guess where the body starts")
    end = text.index("\n---\n", 4)
    return text[end + 5:].lstrip("\n")


def build() -> str:
    parts = [strip_frontmatter(show("SKILL.md")).rstrip("\n")]
    for ref in REFS:
        parts.append(f"# {ref}\n\n{show(ref).strip()}")
    return "\n\n".join(parts) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed file differs from a fresh build")
    o = ap.parse_args()
    text = build()
    digest = hashlib.sha256(text.encode()).hexdigest()
    if o.check:
        if OUT.read_text() != text:
            sys.exit(f"{OUT.relative_to(REPO)} differs from a fresh build of {TAG}")
        print(f"ok {digest}")
        return
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(REPO)}: {len(text.split())} words, sha256 {digest}")


if __name__ == "__main__":
    main()
