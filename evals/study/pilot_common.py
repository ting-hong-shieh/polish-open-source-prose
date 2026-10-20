"""Shared pieces of the pilot pipeline (evals/study/PILOT_DESIGN.md): paths, cases, evidence
files, the CI summary, prompt assembly, and the output parser.

Every path can be overridden by an environment variable so the same scripts run on another
machine; the defaults are this machine's layout.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
PROC = DATA / "Processed/polish-open-source-prose"
EXPORTS = DATA / "Exports/polish-open-source-prose"
PILOT = Path(os.environ.get("PILOT_ROOT", EXPORTS / "study-runs/pilot"))
EVIDENCE = Path(os.environ.get("EVIDENCE_DIR", PROC / "round4-cases"))
CASES_FILE = Path(os.environ.get("CASES_FILE", PROC / "heldout-a2-cases.json"))
SKILL_TEMPLATE = Path(os.environ.get("SKILL_TEMPLATE", EXPORTS / "eval-runs-2026-10-04/round3/claude-workdir-skill"))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/home/elias-shieh/.claude/remote/ccd-cli/2.1.293-63201613aae3")
CLAUDE_VERSION = os.environ.get("CLAUDE_VERSION", "2.1.293")

MODELS = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1"]
EVIDENCE_LEVELS = ["E0", "E_code", "E1"]
INSTRUCTIONS = ["none", "compact", "skill"]
RUNS = ["1", "2"]
SLASH = "/polish-open-source-prose-v020 "
COMPACT = (REPO / "evals/prompts/three-sentences.txt").read_text().strip()
CODE_PARAGRAPH = (REPO / "evals/prompts/round4-code-paragraph.txt").read_text().strip()
EVIDENCE_PARAGRAPH = (REPO / "evals/prompts/round4-evidence-paragraph.txt").read_text().strip()
# Cases whose diff.patch exceeds 1,000 lines get judge batches of 5 (PILOT_PLAN, Judging).
LARGE_DIFF_LINES = 1000
NON_SUCCESS = {"failure", "cancelled", "timed_out", "action_required", "stale", "startup_failure"}


def arm(evidence: str, instruction: str) -> str:
    return f"{evidence}__{instruction}"


def read_cases() -> dict[str, dict]:
    """The A2 cases, refusing a file whose SHA-256 differs from the committed manifest."""
    raw = CASES_FILE.read_bytes()
    expected = json.loads((REPO / "evals/heldout/a2_manifest.json").read_text())["sha256"]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise SystemExit(f"{CASES_FILE} does not match evals/heldout/a2_manifest.json")
    return {c["id"]: c for c in json.loads(raw)["cases"]}


def review_body(case_id: str) -> str:
    text = (EVIDENCE / case_id / "review.md").read_text()
    return text.split("\n---\n", 1)[1].strip()


def review_header(case_id: str) -> dict:
    head = (EVIDENCE / case_id / "review.md").read_text().split("\n---\n", 1)[0]
    return dict(line.split(": ", 1) for line in head.splitlines() if ": " in line)


def diff_text(case_id: str) -> str:
    return (EVIDENCE / case_id / "diff.patch").read_text()


def diff_lines(case_id: str) -> int:
    return diff_text(case_id).count("\n")


def ci_summary(case_id: str) -> str:
    """Two parts: one line of counts and combined status, then the non-success checks."""
    rows = []
    status = "unknown"
    for line in (EVIDENCE / case_id / "ci.md").read_text().splitlines():
        if line.startswith("Combined commit status: "):
            status = line.split(": ", 1)[1]
        m = re.match(r"\| (.+?) \| (\w+) \|$", line)
        if m and m.group(1) != "Check":
            rows.append((m.group(1), m.group(2)))
    counts: dict[str, int] = {}
    for _, c in rows:
        counts[c] = counts.get(c, 0) + 1
    order = sorted(counts, key=lambda k: (-counts[k], k))
    out = [f"{len(rows)} check runs: " + ", ".join(f"{k} {counts[k]}" for k in order) + f"; combined status: {status}."]
    bad = [f"- {name}: {c}" for name, c in rows if c in NON_SUCCESS]
    if bad:
        out.append("Checks that did not succeed:")
        out += bad
    else:
        out.append("No check failed or was cancelled.")
    out.append("The full list is in ci.md.")
    return "\n".join(out)


def task_prompt(case: dict) -> str:
    """The round-3 Claude task prompt, verbatim (PILOT_DESIGN §2)."""
    return (f"Revise the following text. Surface: {case['surface']}. Target locale: en. "
            "Put the complete revised text between <revised> and </revised>; "
            "you may add a brief note outside the tags.\n\n"
            f"<text>\n{case['input']}\n</text>")


def evidence_paragraph(evidence: str, case_id: str) -> str:
    if evidence == "E0":
        return ""
    if evidence == "E_code":
        return CODE_PARAGRAPH.replace("{ci}", ci_summary(case_id))
    if evidence == "E1":
        return EVIDENCE_PARAGRAPH.replace("{review}", review_body(case_id)).replace("{ci}", ci_summary(case_id))
    raise ValueError(evidence)


def full_prompt(case: dict, evidence: str, instruction: str) -> str:
    """Instruction → evidence paragraph → task prompt. The slash command goes in front for
    the skill condition, as in rounds 2–3."""
    blocks = []
    if instruction == "compact":
        blocks.append(COMPACT)
    para = evidence_paragraph(evidence, case["id"])
    if para:
        blocks.append(para)
    blocks.append(task_prompt(case))
    text = "\n\n".join(blocks)
    return SLASH + text if instruction == "skill" else text


# Output parsing, as in evals/score_benchmark.py (line-anchored tags first).
LEGACY_TAGS = re.compile(r"<revised>\s*\n?(.*?)\n?\s*</revised>", re.S)
LINE_TAGS = re.compile(r"^[ \t]*<revised>[ \t]*\n(.*?)\n?[ \t]*</revised>[ \t]*$", re.S | re.M)


def split_output(raw: str) -> tuple[str | None, str]:
    m = LINE_TAGS.search(raw) or LEGACY_TAGS.search(raw)
    if not m:
        return None, raw.strip()
    return m.group(1), (raw[:m.start()] + raw[m.end():]).strip()


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).replace("\r\n", "\n").rstrip("\n")


def normalized(s: str) -> str:
    return "\n".join(line.rstrip() for line in nfc(s).strip().splitlines())
