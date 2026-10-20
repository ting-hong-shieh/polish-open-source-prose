#!/bin/bash
# Pilot full run: drive, verify, delete bad run directories, repeat until all runs pass or
# the retry budget is spent. Start with nohup so it survives the controlling session.
#   POLISH_EVAL_DATA=/mnt/d/Data nohup bash evals/study/run_pilot.sh > "$PILOT_ROOT/full-run.log" 2>&1 &
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
EXPECT="${EXPECT:-1512}"
ROOT="$($PY -I -c 'import sys; sys.path.insert(0, "'"$HERE"'"); import pilot_common as pc; print(pc.PILOT)')"
for attempt in 1 2 3 4 5; do
  echo "=== attempt $attempt: $(date -Is) ==="
  $PY -I "$HERE/drive.py" "$@"
  echo "=== verify: $(date -Is) ==="
  if $PY -I "$HERE/verify_runs.py" --quiet --expect "$EXPECT" > "$ROOT/verify-attempt$attempt.txt" 2>&1; then
    echo "ALL $EXPECT RUNS PASS: $(date -Is)"; echo DONE > "$ROOT/full-run.status"; exit 0
  fi
  tail -5 "$ROOT/verify-attempt$attempt.txt"
  mapfile -t BAD < <($PY -I "$HERE/verify_runs.py" --list-bad)
  echo "deleting ${#BAD[@]} bad run directories"
  for d in "${BAD[@]}"; do
    case "$d" in "$ROOT"/runs/claude/*) rm -rf "$d"; echo "  rm $d";; *) echo "  REFUSED $d";; esac
  done
done
echo "RETRY BUDGET SPENT: $(date -Is)"; echo FAILED > "$ROOT/full-run.status"; exit 1
