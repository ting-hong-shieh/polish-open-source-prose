#!/usr/bin/env python3
"""Check the main study's execution environment (STUDY_PLAN §4, Execution environment).

Runs the pinned Claude Code build with the dedicated configuration directory and a minimal
process environment, twice:
  1. `/context` (a local command; no model call): lists memory files, skills, and plugins;
  2. one real dry run, Haiku 5.5, E0 × none, on one case with the main-study prompt.
It saves both stream-json outputs and fails if the context holds a user memory file
(CLAUDE.md), a plugin, a user skill, or an auto-memory path, or if the account is not
signed in. Outputs (they hold the case text) go outside Git:
$POLISH_EVAL_DATA/Exports/polish-open-source-prose/study-runs/config-check/clean-<timestamp>/

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/study/check_clean_config.py [--case ID] [--context-only]
Sign in first, once:  CLAUDE_CONFIG_DIR=$HOME/.claude-study <claude build> auth login
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

CONFIG_DIR = Path(os.environ.get("STUDY_CLAUDE_CONFIG_DIR", Path.home() / ".claude-study"))
# Skills whose /context source is "Built-in" ship with the build (the list changes with sign-in:
# `schedule` appears once a claude.ai account is signed in). Any other source (user settings,
# plugin, synced account skills) is a failure.
BUILTIN_SOURCES = {"Built-in", "Bundled"}


def clean_env() -> dict[str, str]:
    """Home, path, locale, and the configuration directory only."""
    return {"HOME": str(Path.home()), "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
            "CLAUDE_CONFIG_DIR": str(CONFIG_DIR)}


def run(args: list[str], stdin: str, cwd: Path, env: dict | None = None) -> list[dict]:
    p = subprocess.run([pc.CLAUDE_BIN, *args], input=stdin, capture_output=True, text=True, cwd=cwd,
                       env=env or clean_env(), timeout=600)
    events = []
    for line in p.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return events


def context_skills(text: str) -> dict[str, str]:
    """{skill: source} from the Skills table of a /context result."""
    m = re.search(r"### Skills.*?(?=\n### |\Z)", text, re.S)
    rows = re.findall(r"^\| ([^|]+?) \| ([^|]+?) \| [^|]*\|$", m.group(0), re.M) if m else []
    return {name.strip(): src.strip() for name, src in rows if name.strip() not in ("Skill", "-------")}


def check_init(events: list[dict], problems: list[str], slash_enabled: bool, builtin: set[str]) -> dict:
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    if not init:
        problems.append("no init event")
        return {}
    if init.get("plugins"):
        problems.append(f"plugins loaded: {[p.get('name') for p in init['plugins']]}")
    if init.get("memory_paths"):
        problems.append(f"auto-memory path present: {init['memory_paths']}")
    extra = [s for s in init.get("skills") or [] if s not in builtin]
    if extra:
        problems.append(f"user skills listed: {extra}")
    if not slash_enabled and init.get("skills"):
        problems.append("skills listed although slash commands are disabled")
    if init.get("claude_code_version") != pc.CLAUDE_VERSION:
        problems.append(f"build {init.get('claude_code_version')} != {pc.CLAUDE_VERSION}")
    return init


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="a2-airflow-60733")
    ap.add_argument("--context-only", action="store_true")
    o = ap.parse_args()
    out = pc.EXPORTS / "study-runs/config-check" / time.strftime("clean-%Y%m%dT%H%M%S")
    work = out / "work"
    work.mkdir(parents=True)
    problems: list[str] = []
    base = ["-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--strict-mcp-config",
            "--allowedTools", "Read", "--tools", "Read,Skill", "--permission-mode", "default"]

    ctx = run([*base, "--model", "claude-haiku-5-5"], "/context", work)
    (out / "context.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ctx))
    text = next((str(e.get("result")) for e in ctx if e.get("type") == "result"), "")
    skills = context_skills(text)
    # The build's own skill list: what an empty, signed-out configuration directory lists (no model call).
    with tempfile.TemporaryDirectory() as empty:
        base_ev = run([*base, "--model", "claude-haiku-5-5"], "x", work, env=dict(clean_env(), CLAUDE_CONFIG_DIR=empty))
    baseline = set(next((e.get("skills") or [] for e in base_ev if e.get("subtype") == "init"), []))
    builtin = {k for k, v in skills.items() if v in BUILTIN_SOURCES} | baseline
    other = {k: v for k, v in skills.items() if v not in BUILTIN_SOURCES}
    if other:
        problems.append(f"skills from outside the build: {other}")
    print(f"/context: {len(skills) - len(other)} built-in skills, {len(other)} from elsewhere; "
          f"signed-out baseline lists {len(baseline)}")
    check_init(ctx, problems, slash_enabled=True, builtin=builtin)
    if "### Memory Files" in text:
        problems.append("memory files listed: " + re.search(r"### Memory Files.*?(?=\n### |\Z)", text, re.S).group(0))
    if "### MCP" in text:
        problems.append("MCP tools listed")

    if not o.context_only:
        case = pc.read_cases()[o.case]
        prompt = pc.study_prompt(case, "E0", "none")
        (out / "prompt.txt").write_text(prompt)
        ev = run([*base, "--disable-slash-commands", "--model", "claude-haiku-5-5", "--effort", "high"], prompt, work)
        (out / "dry-run.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ev))
        check_init(ev, problems, slash_enabled=False, builtin=builtin)
        res = next((e for e in ev if e.get("type") == "result"), {})
        if res.get("is_error") or "Not logged in" in str(res.get("result")):
            problems.append(f"run failed: {str(res.get('result'))[:200]}")
        revised, _ = pc.split_output(str(res.get("result") or ""))
        print(f"dry run: cost {res.get('total_cost_usd')}, parsed <revised>: {revised is not None}")

    (out / "check.json").write_text(json.dumps({"config_dir": str(CONFIG_DIR), "env_keys": sorted(clean_env()),
                                                "settings": json.loads((CONFIG_DIR / "settings.json").read_text()),
                                                "context_skills": skills, "baseline_skills": sorted(baseline),
                                                "problems": problems}, indent=1) + "\n")
    print(f"-> {out}")
    print("PASS: no user memory file, plugin, user skill, MCP server, or auto-memory path in context"
          if not problems else "FAIL:\n  " + "\n  ".join(problems))
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
