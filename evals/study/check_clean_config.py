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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

CONFIG_DIR = Path(os.environ.get("STUDY_CLAUDE_CONFIG_DIR", Path.home() / ".claude-study"))
# The build's own bundled skills (listed when slash commands are enabled); anything else is a user skill.
BUNDLED = {"deep-research", "design", "design-sync", "dataviz", "update-config", "verify", "debug", "code-review",
           "simplify", "batch", "fewer-permission-prompts", "doctor", "loop", "claude-api", "workflow-authoring",
           "run", "run-skill-generator"}


def clean_env() -> dict[str, str]:
    """Home, path, locale, and the configuration directory only."""
    return {"HOME": str(Path.home()), "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
            "CLAUDE_CONFIG_DIR": str(CONFIG_DIR)}


def run(args: list[str], stdin: str, cwd: Path) -> list[dict]:
    p = subprocess.run([pc.CLAUDE_BIN, *args], input=stdin, capture_output=True, text=True, cwd=cwd,
                       env=clean_env(), timeout=600)
    events = []
    for line in p.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return events


def check_init(events: list[dict], problems: list[str], slash_enabled: bool) -> dict:
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    if not init:
        problems.append("no init event")
        return {}
    if init.get("plugins"):
        problems.append(f"plugins loaded: {[p.get('name') for p in init['plugins']]}")
    if init.get("memory_paths"):
        problems.append(f"auto-memory path present: {init['memory_paths']}")
    extra = [s for s in init.get("skills") or [] if s not in BUNDLED]
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
    check_init(ctx, problems, slash_enabled=True)
    text = next((str(e.get("result")) for e in ctx if e.get("type") == "result"), "")
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
        check_init(ev, problems, slash_enabled=False)
        res = next((e for e in ev if e.get("type") == "result"), {})
        if res.get("is_error") or "Not logged in" in str(res.get("result")):
            problems.append(f"run failed: {str(res.get('result'))[:200]}")
        revised, _ = pc.split_output(str(res.get("result") or ""))
        print(f"dry run: cost {res.get('total_cost_usd')}, parsed <revised>: {revised is not None}")

    (out / "check.json").write_text(json.dumps({"config_dir": str(CONFIG_DIR), "env_keys": sorted(clean_env()),
                                                "problems": problems}, indent=1) + "\n")
    print(f"-> {out}")
    print("PASS: no user memory file, plugin, user skill, MCP server, or auto-memory path in context"
          if not problems else "FAIL:\n  " + "\n  ".join(problems))
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
