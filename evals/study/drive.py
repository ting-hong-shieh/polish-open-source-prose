#!/usr/bin/env python3
"""Pilot driver: enumerate (model, evidence, instruction, run, case) and run the jobs through
run_claude.py, one pool per model. Finished runs are skipped by the runner, so it can be
rerun. Writes versions.txt once and log-<model>.txt per model under $PILOT_ROOT.

Usage: drive.py [--models m1,m2] [--evidence E0,E_code,E1] [--instructions none,compact,skill]
                [--runs 1,2] [--only CASE] [--workers 3] [--dry-run]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_common as pc  # noqa: E402

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(pc.MODELS))
    ap.add_argument("--evidence", default=",".join(pc.EVIDENCE_LEVELS))
    ap.add_argument("--instructions", default=",".join(pc.INSTRUCTIONS))
    ap.add_argument("--runs", default=",".join(pc.RUNS))
    ap.add_argument("--only")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    o = ap.parse_args()
    cases = [c for c in pc.read_cases() if not o.only or c == o.only]
    if not cases:
        raise SystemExit(f"no case {o.only!r}")
    pc.PILOT.mkdir(parents=True, exist_ok=True)
    versions = pc.PILOT / "versions.txt"
    if not o.dry_run and not versions.exists():
        v = subprocess.run([pc.CLAUDE_BIN, "--version"], capture_output=True, text=True, timeout=60).stdout.strip()
        versions.write_text(f"claude\t{pc.CLAUDE_BIN}\t{v}\nskill-template\t{pc.SKILL_TEMPLATE}\nevidence\t{pc.EVIDENCE}\n")
    for model in o.models.split(","):
        jobs = [[sys.executable, "-I", str(HERE / "run_claude.py"), model, ev, ins, run, cid]
                for ev in o.evidence.split(",") for ins in o.instructions.split(",") for run in o.runs.split(",")
                for cid in cases]
        print(f"[{model}] {len(jobs)} jobs", flush=True)
        if o.dry_run:
            continue
        log = pc.PILOT / f"log-{model}.txt"
        with log.open("a") as lf, concurrent.futures.ThreadPoolExecutor(o.workers) as pool:
            def one(j):
                p = subprocess.run(j, capture_output=True, text=True)
                lf.write(p.stdout + (p.stderr if p.returncode else ""))
                lf.flush()
                return p.returncode
            rcs = list(pool.map(one, jobs))
        print(f"[{model}] done, nonzero exits: {sum(1 for r in rcs if r)}", flush=True)


if __name__ == "__main__":
    main()
