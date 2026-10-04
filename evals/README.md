# Evaluations

This directory holds the scripts, prompts, and scored results behind the numbers in
the README. Large or private data lives outside Git; this file says where and why.

## Layout

| Path | Contents | In Git |
| --- | --- | --- |
| `evals/score_runs.py` | Scores the 2026-10-04 model runs and writes `results/runs-2026-10-04.json` | Yes |
| `evals/results/runs-2026-10-04.json` | Every scored output: model, condition, run, case, pass, and the revised text | Yes |
| `evals/prompts/` | The one-sentence and three-sentence instructions used as baselines | Yes |
| `evals/collect_review_threads.py` | Collects public pull request threads where reviewers criticized prose or claims | Yes |
| `$POLISH_EVAL_DATA/Exports/polish-open-source-prose/eval-runs-2026-10-04/` | Raw model runs: prompts, outputs, event logs, the original reports and runners | No |
| `$POLISH_EVAL_DATA/Raw/polish-open-source-prose/github-threads/` | Raw pull request threads collected from GitHub | No |
| `$POLISH_EVAL_DATA/Processed/polish-open-source-prose/` | Labels derived from those threads | No |

`POLISH_EVAL_DATA` defaults to `/mnt/d/Data`. Set it to wherever the data folder lives on
another machine.

Raw data stays out of Git for three reasons: event logs contain local paths and session
identifiers; the GitHub threads are other people's text and usernames; and the original
Codex runs were large. Publish only aggregate counts and links to public pull requests
from the GitHub threads, never their text.

## 2026-10-04 model runs

Each of the 49 forward cases at commit `2a05713` was given to three models with an
instruction to revise it, under five conditions: no skill, the one-sentence instruction,
the three-sentence instruction, v0.1.0, and v0.2.0. Claude Opus 5.5 ran in Claude Code
twice per condition; GPT-6.1 Sol and GPT-6 Astra ran in Codex once per condition.

To rescore from the raw runs:

```bash
POLISH_EVAL_DATA=/mnt/d/Data python3 evals/score_runs.py
```

Limits are listed in the README's "How we tested it" section. In short: the cases and
expected results were written by the maintainer, scoring checks literal strings, and the
GPT models ran once.

The runners that produced the raw runs are archived with the data, not here. They contain
machine-specific paths and were written for this one run.

## Review threads

`collect_review_threads.py` searches pull request comments in a few repositories for
phrases such as "AI-generated", "LLM", and "provide evidence", then saves each matching
thread with its description edit history and title renames.

```bash
POLISH_EVAL_DATA=/mnt/d/Data python3 evals/collect_review_threads.py --since 2025-10-01
```

Phrase search only finds reviewers who said so explicitly, so the threads show what
reviewers object to, not how often the problems occur.
