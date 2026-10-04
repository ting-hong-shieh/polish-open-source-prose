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
| `evals/heldout/a1_cases.json` | Held-out set A1: 24 cases written after v0.2.0 and frozen before any run | Yes |
| `evals/heldout/a2_manifest.json` | Held-out set A2: URLs and SHA-256 of 21 real pull request cases | Yes |
| `evals/heldout/extract_real_pairs.py`, `build_a2_cases.py` | Build the A2 cases from the collected threads | Yes |
| `evals/score_benchmark.py` | Scores every run on the development set, A1, and A2 with literal checks | Yes |
| `evals/judge_outputs.py` | Has two judge models grade the held-out edits and every changed keep output, blind | Yes |
| `evals/analyze_benchmark.py` | Aggregates, tests, and draws the figures and tables for the report | Yes |
| `evals/results/benchmark.json`, `judgments.json`, `analysis.json` | Scored outputs (development set and A1), judge labels, and aggregates | Yes |
| `evals/results/judgments-a1-notes-hidden.json` | A first judging pass on A1 edits, before judges saw the editor's note | Yes |
| `docs/report/` | The benchmark report (LaTeX source, figures, generated tables, PDF) | Yes |
| `$POLISH_EVAL_DATA/Processed/polish-open-source-prose/heldout-a2-cases.json` | The A2 case text | No |
| `$POLISH_EVAL_DATA/Processed/polish-open-source-prose/benchmark-a2.json` | Scored A2 outputs | No |
| `$POLISH_EVAL_DATA/Processed/polish-open-source-prose/judgments-a2.json` | Judge labels for A2, which can quote the A2 text | No |
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

## 2026-10-05 benchmark

The report in `docs/report/` extends the runs above to seven model configurations (Claude
Opus 5.5, Opus 4.6, and Sonnet 5.5 at high effort; GPT-6.1 Sol at high; GPT-6 Astra at high
and low; GPT-6 Luna at max) and adds two held-out sets. A1 was committed at `fa993da`
before any model ran on it. A2 holds third-party text, so only its manifest is in Git; the
manifest was committed at `502484f` before any run, and its SHA-256 must match the case
file.

The runs are under `round2/` in the raw-run folder (`runs/` for the development set,
`runs-a1/`, and `runs-a2/`). To rebuild the report from them:

```bash
POLISH_EVAL_DATA=/mnt/d/Data python3 evals/score_benchmark.py
POLISH_EVAL_DATA=/mnt/d/Data python3 evals/judge_outputs.py --judge both
POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/analyze_benchmark.py
tectonic docs/report/report.tex
```

`judge_outputs.py` skips judgments already in `results/judgments.json`. `analyze_benchmark.py`
needs matplotlib and numpy; install them in a local `.venv`, which Git ignores.
