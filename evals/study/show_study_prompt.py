#!/usr/bin/env python3
"""Dry run of the main-study prompt assembly (STUDY_PLAN §4) for one case: prints every
prompt the editor would receive, with the working-directory files and the Claude Code
command, for each evidence level and instruction condition. No model is called.

The output holds the case's third-party text, so it is written outside Git:
$POLISH_EVAL_DATA/Processed/polish-open-source-prose/study-prompt-dryrun/<case>.md

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/study/show_study_prompt.py CASE_ID
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

FILES = {"E0": [], "E_code": ["diff.patch", "ci.md"], "E1": ["diff.patch", "ci.md", "review.md"]}
ARMS = [(ev, ins) for ev in pc.EVIDENCE_LEVELS for ins in pc.STUDY_INSTRUCTIONS
        if not (ins == "compact_check" and ev == "E0")]


def command(model: str, instruction: str) -> list[str]:
    args = [Path(pc.CLAUDE_BIN).name, "-p", "--model", model, "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--strict-mcp-config", "--allowedTools", "Read", "--tools", "Read,Skill",
            "--effort", "high"]
    return args + ([] if instruction == "skill" else ["--disable-slash-commands"])


def main() -> None:
    cid = sys.argv[1]
    case = pc.read_cases()[cid]
    out = pc.PROC / "study-prompt-dryrun" / f"{cid}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"# Study prompt dry run: {cid}\n",
             "No model was called. Each section is the exact text sent on stdin. "
             "Prompts come from evals/prompts/study-task-*.txt, three-sentences.txt and compact-check.txt.\n",
             f"Diff: {pc.diff_lines(cid)} patch lines. Arms: {len(ARMS)}.\n"]
    for ev, ins in ARMS:
        work = (["the v0.2.0 skill under .claude/skills/"] if ins == "skill" else []) + FILES[ev]
        prompt = pc.study_prompt(case, ev, ins)
        parts.append(f"## {ev} × {ins}\n\n- working directory: {', '.join(work) or '(empty)'}\n"
                     f"- command: `{' '.join(command('MODEL', ins))}`\n- prompt: {len(prompt):,} characters\n\n"
                     f"````text\n{prompt}\n````\n")
    out.write_text("\n".join(parts))
    print(f"{len(ARMS)} prompts -> {out}")


if __name__ == "__main__":
    main()
