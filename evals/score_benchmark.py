#!/usr/bin/env python3
"""Score every benchmark run and write evals/results/benchmark.json.

Two case sets:
- "main": the 49 forward cases at commit 2a05713 (the skill was developed against them).
- "a1": the 24 held-out cases frozen at commit fa993da before any model ran on them.

Raw runs live outside Git under
$POLISH_EVAL_DATA/Exports/polish-open-source-prose/eval-runs-2026-10-04 (see
evals/README.md). One literal rule applies to every model and condition: NFC,
case-sensitive substrings; a keep case passes only if the output equals the input.
Claude Code runs return the revision inside <revised> tags and may add a note to the author
outside them, which is kept as "note"; Codex runs return the revision alone.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 evals/score_benchmark.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import unicodedata
from collections import defaultdict
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[1]
RUNS = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data")) / "Exports/polish-open-source-prose/eval-runs-2026-10-04"
R2 = "round2"
CONDITIONS = ["no_skill", "one_sentence", "three_sentences", "v0.1.0", "v0.2.0"]
# Round 3 (see evals/round3/PLAN.md) runs on the held-out sets only, in the same layout as
# round 2 under a separate root, and is scored whenever that root exists. It adds two
# conditions and reruns two round-2 conditions as same-batch comparators. Directory names
# follow the runners; the reruns get their own condition labels so they never mix with the
# round-2 outputs of the same condition.
R3 = "round3"
R3_CONDITIONS = {"compact_problems": "compact_problems", "skill_inline": "skill_inline",
                 "three_sentences_r3": "three_sentences", "v0.2.0_r3": "v0.2.0"}  # label -> directory
WITH_R3 = (RUNS / R3).is_dir()


def claude_r2(set_dir: str, model: str, conds=CONDITIONS, root: str = R2) -> dict:
    dirs = conds if isinstance(conds, dict) else {c: c for c in conds}
    return {c: [f"{root}/{set_dir}/claude/{model}/{d}/run{r}/{{id}}/result.txt" for r in (1, 2)] for c, d in dirs.items()}


def codex_r2(set_dir: str, tag: str, conds=CONDITIONS, root: str = R2) -> dict:
    dirs = conds if isinstance(conds, dict) else {c: c for c in conds}
    return {c: [f"{root}/{set_dir}/codex/{tag}/{d}/{{id}}/output.txt"] for c, d in dirs.items()}


def heldout(set_dir: str, key: tuple) -> dict:
    model, effort, platform = key
    if platform == "claude":
        out = claude_r2(set_dir, model)
        if WITH_R3:
            out.update(claude_r2(set_dir, model, R3_CONDITIONS, R3))
        return out
    tag = "gpt-6-astra@low" if effort == "low" else model
    out = codex_r2(set_dir, tag)
    if WITH_R3:
        out.update(codex_r2(set_dir, tag, R3_CONDITIONS, R3))
    return out


# (model, effort, platform) -> condition -> list of path templates, one per run
MAIN = {
    ("claude-opus-5-5", "high", "claude"): {
        "no_skill": ["claude-next/runs/A/{id}/result.txt", "claude-next/runs/A2/{id}/result.txt"],
        "one_sentence": ["claude-next/runs/Q/{id}/result.txt", "claude-next/runs/Q2/{id}/result.txt"],
        "three_sentences": ["claude-next/runs/P/{id}/result.txt", "claude-next/runs/P2/{id}/result.txt"],
        "v0.1.0": ["claude-raw/runs/B/{id}/result.txt", "claude-raw/runs/B2/{id}/result.txt"],
        "v0.2.0": [f"{R2}/runs/claude/claude-opus-5-5/v0.2.0/run{r}/{{id}}/result.txt" for r in (1, 2)],
    },
    ("claude-opus-4-6", "high", "claude"): claude_r2("runs", "claude-opus-4-6"),
    ("claude-sonnet-5-5", "high", "claude"): claude_r2("runs", "claude-sonnet-5-5"),
    ("gpt-6.1-sol", "high", "codex"): {
        "no_skill": ["codex-raw/runs/{id}/A/output.txt"],
        "one_sentence": ["codex-c1-sol/runs/{id}/P/output.txt"],
        "three_sentences": ["codex-p-sol/runs/{id}/P/output.txt"],
        "v0.1.0": ["codex-raw/runs/{id}/B/output.txt"],
        "v0.2.0": [f"{R2}/runs/codex/gpt-6.1-sol/v0.2.0/{{id}}/output.txt"],
    },
    ("gpt-6-astra", "high", "codex"): codex_r2("runs", "gpt-6-astra"),
    ("gpt-6-astra", "low", "codex"): codex_r2("runs", "gpt-6-astra@low"),
    ("gpt-6-luna", "max", "codex"): codex_r2("runs", "gpt-6-luna"),
}
A2 = {key: heldout("runs-a2", key) for key in MAIN}
A1 = {key: heldout("runs-a1", key) for key in MAIN}
SETS = {"main": ("2a05713", "skills/polish-open-source-prose/tests/forward_cases.json", MAIN),
        "a1": ("fa993da", "evals/heldout/a1_cases.json", A1),
        "a2": (None, "Processed/polish-open-source-prose/heldout-a2-cases.json", A2)}
# A2 holds third-party text: its per-output records stay under $POLISH_EVAL_DATA.
A2_RECORDS = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data")) / "Processed/polish-open-source-prose/benchmark-a2.json"


def read_a2_cases(path: Path) -> list[dict]:
    """Load the private A2 cases, refusing a file whose SHA-256 differs from the committed manifest."""
    raw = path.read_bytes()
    expected = json.loads((REPO / "evals/heldout/a2_manifest.json").read_text())["sha256"]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise SystemExit(f"{path} does not match the SHA-256 in evals/heldout/a2_manifest.json")
    return json.loads(raw)["cases"]


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).replace("\r\n", "\n").rstrip("\n")


def lines(s: str) -> str:
    return "\n".join(l.rstrip() for l in nfc(s).strip().splitlines())


LEGACY_TAGS = re.compile(r"<revised>\s*\n?(.*?)\n?\s*</revised>", re.S)
# A tag on a line of its own. An editor that mentions "<revised>" inside its explanation
# (one A1 Sonnet 5.5 v0.1.0 output did) must not be mistaken for the opening tag.
LINE_TAGS = re.compile(r"^[ \t]*<revised>[ \t]*\n(.*?)\n?[ \t]*</revised>[ \t]*$", re.S | re.M)
PARSER_CHANGES: list[str] = []


def revised(raw: str, case: dict, platform: str, where: str = "") -> tuple[str, str]:
    """Split an output into the revised text and any note to the author outside the tags."""
    if platform == "claude" and case["mode"] != "provenance":
        m = LINE_TAGS.search(raw) or LEGACY_TAGS.search(raw)
        legacy = LEGACY_TAGS.search(raw)
        if legacy and m and m.group(1) != legacy.group(1):
            PARSER_CHANGES.append(where)
        if m:
            return m.group(1), (raw[:m.start()] + raw[m.end():]).strip()
    return raw, ""


def score(case: dict, text: str) -> tuple[bool, bool]:
    t = nfc(text)
    unchanged = lines(text) == lines(case["input"])
    ok = all(nfc(s) in t for s in case["must_preserve"])
    ok = ok and not any(nfc(s) in t for s in case["must_remove"])
    ok = ok and not any(nfc(s) in t and s not in case["input"] for s in case["must_not_introduce"])
    return (ok and unchanged) if case["mode"] == "keep" else ok, unchanged


def main() -> None:
    records, summary, missing = [], defaultdict(dict), []
    for set_name, (commit, path, layout) in SETS.items():
        if commit is None:
            src = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data")) / path
            if not src.exists():
                continue
            cases = read_a2_cases(src)
        else:
            cases = json.loads(subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=REPO, text=True))["cases"]
        for (model, effort, platform), conds in layout.items():
            label = f"{model}@{effort}"
            for cond, templates in conds.items():
                runs = []
                for k, tpl in enumerate(templates, 1):
                    groups = defaultdict(list)
                    for case in cases:
                        f = RUNS / tpl.format(id=case["id"])
                        if not f.exists():
                            missing.append(str(f.relative_to(RUNS)))
                            continue
                        text, note = revised(f.read_text(), case, platform, str(f.relative_to(RUNS)))
                        ok, unchanged = score(case, text)
                        kind = "keep" if case["mode"] == "keep" else "edit"
                        for g in (kind, f"{case['locale']}/{kind}"):
                            groups[g].append(ok)
                        records.append({"set": set_name, "model": model, "effort": effort, "condition": cond,
                                        "run": k, "case": case["id"], "locale": case["locale"],
                                        "mode": case["mode"], "pass": ok, "unchanged": unchanged, "output": text,
                                        "note": note})
                    runs.append({g: [sum(v), len(v)] for g, v in groups.items()})
                summary[set_name].setdefault(label, {})[cond] = {
                    "runs": runs,
                    "mean_pass": {g: round(mean(r[g][0] for r in runs), 2) for g in runs[0]},
                    "n": {g: runs[0][g][1] for g in runs[0]},
                }
    public = [r for r in records if r["set"] != "a2"]
    A2_RECORDS.write_text(json.dumps({"records": [r for r in records if r["set"] == "a2"]},
                                     ensure_ascii=False, indent=1) + "\n")
    out = REPO / "evals/results/benchmark.json"
    out.write_text(json.dumps({"case_commits": {"main": "2a05713", "a1": "fa993da",
                                                "a2": "private; see evals/heldout/a2_manifest.json"},
                               "summary": summary, "records": public}, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(records)} records; {len(missing)} missing outputs; round 3 {'included' if WITH_R3 else 'not found'}")
    # Expected: exactly one, the A1 Sonnet 5.5 v0.1.0 output described in the report.
    print(f"{len(PARSER_CHANGES)} outputs parsed differently from the legacy tag regex")
    for w in PARSER_CHANGES:
        print("  parser change:", w)
    for m in missing[:10]:
        print("  missing:", m)


if __name__ == "__main__":
    main()
