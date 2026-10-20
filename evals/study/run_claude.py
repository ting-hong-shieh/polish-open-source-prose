#!/usr/bin/env python3
"""One pilot run in Claude Code (evals/study/PILOT_DESIGN.md §3).

Builds a working directory for the run, assembles the prompt, calls the pinned Claude Code
build with the round-2/3 flags, and writes prompt.txt, command.json, stream.jsonl,
stderr.txt, result.txt, and meta.json under
$PILOT_ROOT/runs/claude/<model>/<evidence>__<instruction>/run<r>/<case>/.

Usage: run_claude.py MODEL EVIDENCE INSTRUCTION RUN CASE_ID
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

EVIDENCE_FILES = {"E0": [], "E_code": ["diff.patch", "ci.md"], "E1": ["diff.patch", "ci.md", "review.md"]}


def build_workdir(work: Path, evidence: str, instruction: str, case_id: str) -> None:
    if instruction == "skill":
        shutil.copytree(pc.SKILL_TEMPLATE, work, symlinks=True)
    else:
        work.mkdir()
    for name in EVIDENCE_FILES[evidence]:
        shutil.copy(pc.EVIDENCE / case_id / name, work / name)


def main() -> None:
    model, evidence, instruction, run, cid = sys.argv[1:6]
    assert model in pc.MODELS and evidence in pc.EVIDENCE_LEVELS, sys.argv[1:4]
    assert instruction in pc.INSTRUCTIONS + pc.PROBE_INSTRUCTIONS, instruction
    case = pc.read_cases()[cid]
    d = pc.PILOT / "runs/claude" / model / pc.arm(evidence, instruction) / f"run{run}" / cid
    if (d / "meta.json").exists():
        return
    d.parent.mkdir(parents=True, exist_ok=True)
    try:
        d.mkdir()  # atomic claim, so two job queues never run the same case
    except FileExistsError:
        return
    work = d / "work"
    build_workdir(work, evidence, instruction, cid)
    prompt = pc.full_prompt(case, evidence, instruction)
    (d / "prompt.txt").write_text(prompt)
    base = [pc.CLAUDE_BIN, "-p", "--model", model, "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--strict-mcp-config", "--allowedTools", "Read", "--tools", "Read,Skill"]
    if instruction != "skill":
        base.append("--disable-slash-commands")
    # PILOT_EFFORT sets the level (high in the pilot; medium and low in the effort probe).
    attempts = [(pc.EFFORT, base + ["--effort", pc.EFFORT]), ("default", base)]
    t0 = time.time()
    for effort_used, args in attempts:
        (d / "command.json").write_text(json.dumps(args, indent=1))
        p = subprocess.run(args, input=prompt, capture_output=True, text=True, cwd=work, timeout=1200)
        if p.returncode == 0 or "effort" not in p.stderr.lower():
            break
        (d / f"stderr-effort-{pc.EFFORT}.txt").write_text(p.stderr)  # the model refused the effort level
    (d / "stream.jsonl").write_text(p.stdout)
    (d / "stderr.txt").write_text(p.stderr)
    result, cost, skills, reads, version, usage = None, None, None, [], None, None
    for line in p.stdout.splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            skills = [s for s in (e.get("skills") or []) if "polish" in s]
            version = e.get("claude_code_version")
        elif e.get("type") == "assistant":
            for b in e["message"]["content"]:
                if b["type"] == "tool_use" and b["name"] == "Read":
                    reads.append(b["input"].get("file_path"))
        elif e.get("type") == "result":
            result, cost, usage = e.get("result"), e.get("total_cost_usd"), e.get("usage")
    (d / "result.txt").write_text(result or "")
    revised, note = pc.split_output(result or "")
    meta = {"case": cid, "model": model, "evidence": evidence, "instruction": instruction, "run": run,
            "rc": p.returncode, "seconds": round(time.time() - t0, 1), "cost_usd": cost, "usage": usage,
            "effort_requested": pc.EFFORT, "effort_used": effort_used, "polish_skills_listed": skills, "reads": reads,
            "read_diff": any((r or "").endswith("diff.patch") for r in reads),
            "read_review": any((r or "").endswith("review.md") for r in reads),
            "read_ci": any((r or "").endswith("ci.md") for r in reads),
            "parsed": revised is not None, "claude_code_version": version, "cwd": "work"}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    # The evidence files are copies; drop the work directory's bulk but keep a listing.
    (d / "work-listing.txt").write_text("\n".join(sorted(str(q.relative_to(work)) for q in work.rglob("*"))) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    print(model, evidence, instruction, run, cid, p.returncode, meta["seconds"], cost, "diff" if meta["read_diff"] else "-", flush=True)


if __name__ == "__main__":
    main()
