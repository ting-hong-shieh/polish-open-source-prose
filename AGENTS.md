# Notes for agents working in this repository

- The skill is in `skills/polish-open-source-prose/`. Run `python3 scripts/validate_repo.py`
  after changing it.
- Evaluation data lives outside Git. See `evals/README.md` for where it is and why.
- Never commit files from `$POLISH_EVAL_DATA` (default `/mnt/d/Data`). The GitHub thread
  data is other people's text; the run logs contain local paths and session identifiers.
- A recommended revision in `tests/forward_cases.json` may only use facts that appear in
  the case input.
