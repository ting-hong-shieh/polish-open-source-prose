# Running round 3

`PLAN.md` says what is measured and why. This file is the order of operations. Steps 2 and
4 need model access and the archived round-2 runners, so they run on the machine that holds
`$POLISH_EVAL_DATA`.

## 1. Freeze the plan

Commit `PLAN.md`, the prefix files, and the scripts in this folder before any run (tags
`round3-frozen` and, after Amendment 1, `round3-frozen-2`), then
confirm the inline prefix still matches tag `v0.2.0`:

```bash
python3 evals/round3/build_inline_prompt.py --check
```

## 2. Run the models

Use the round-2 runners archived under
`$POLISH_EVAL_DATA/Exports/polish-open-source-prose/eval-runs-2026-10-04/`. Add the two
conditions the same way `one_sentence` and `three_sentences` were added: a prefix file
prepended to the unchanged task prompt.

| Condition (directory) | Prefix | Skill installed |
| --- | --- | --- |
| `compact_problems` | `evals/prompts/compact-problems.txt` | No |
| `skill_inline` | `evals/prompts/skill-inline-v0.2.0.txt` | No |
| `three_sentences` (rerun) | `evals/prompts/three-sentences.txt` | No |
| `v0.2.0` (rerun) | none | Yes, exactly as in round 2 |

The reruns use the round-2 directory names; scoring labels them `three_sentences_r3` and
`v0.2.0_r3` (PLAN.md, Amendment 1).

Write outputs under `round3/` in the same layout as `round2/`:

```
round3/runs-a1/claude/<model>/<condition>/run{1,2}/<case>/result.txt
round3/runs-a1/codex/<tag>/<condition>/<case>/output.txt
round3/runs-a2/...   (same shape)
```

Keep the saved prompt next to each output, as round 2 did. Run A1 and A2 only, all seven
configurations, two runs for Claude and one for Codex: 1,800 outputs. Record the CLI
versions; if Claude Code or Codex CLI differs from round 2, note it under Deviations in
`PLAN.md`.

## 3. Check the prompts

```bash
POLISH_EVAL_DATA=/mnt/d/Data python3 evals/round3/check_prompts.py --prompt-name <name of the saved prompt file>
```

It must report zero problems before scoring.

## 4. Score and judge

```bash
POLISH_EVAL_DATA=/mnt/d/Data python3 evals/score_benchmark.py
POLISH_EVAL_DATA=/mnt/d/Data python3 evals/judge_outputs.py --judge both --sets a1,a2 --tag round3
```

`score_benchmark.py` should print 6,500 records (4,700 before, plus 1,800) and exactly one
parser change (the A1 Sonnet 5.5 v0.1.0 output the report corrected). Any
other parser change needs a look at its raw output before going further.

The re-judge covers every held-out output in all nine conditions, about 200 judge calls
per judge. The original `judgments.json` and `judgments-a2.json` are not touched.

## 5. Analyze

```bash
POLISH_EVAL_DATA=/mnt/d/Data python3 evals/round3/analyze_round3.py
```

It refuses to run if any required judgment is missing. It writes aggregate numbers only to
`evals/results/round3-analysis.json`, which is safe to commit; the A2 records and labels
stay under `$POLISH_EVAL_DATA`.
