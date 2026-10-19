# Round 3: what the skill's advantage comes from

Written and committed before any round-3 model run. Any change after the first run is
listed under "Deviations" at the end, with the date and the reason.

## Questions

The report found that skill v0.2.0 scored higher than the compact (four-sentence)
instruction on held-out edit cases, and that the two preserved keep cases at similar rates.
It could not say why, because the two conditions differ in content, length, and delivery
at once. Round 3 separates two of these:

- **Q1, content.** Does naming what counts as a problem close the gap? The report's
  discussion suggests the compact instruction fails because it never says what a
  "concrete problem" is.
- **Q2, delivery.** Does the skill mechanism matter, or only its words? The same text
  pasted into the prompt should do as well as the skill if delivery does not matter.

## New conditions

| ID | Prefix file | SHA-256 |
| --- | --- | --- |
| `compact_problems` | `evals/prompts/compact-problems.txt` | `7a57f2f284c0c0deef7e1a7681e0584995bd69593353e63d039d21a793bcc620` |
| `skill_inline` | `evals/prompts/skill-inline-v0.2.0.txt` | `cda3947dc451bd73620b11fecfc50ee88f6aae0e1d195ca57bf0d2a0bdf05837` |

`compact_problems` is the compact instruction, verbatim, plus one sentence naming the three
problem types the report's discussion points to: unsupported certainty, quality claims
without evidence, and test results stretched beyond their scope. It does not tell the
model to ask the author questions, so it adds problem definitions and nothing else.

`skill_inline` is built by `evals/round3/build_inline_prompt.py` from tag `v0.2.0`: the
SKILL.md body without frontmatter, then both reference files verbatim under headings
that repeat the paths SKILL.md links to (1,448 words). `--check` confirms the committed
file matches a fresh build.

Both prefixes are prepended to the task prompt exactly as `one_sentence` and
`three_sentences` were. Neither run directory may contain the skill: no
`.claude/skills` copy, no slash command, no `.agents/skills`, and no `AGENTS.md` line.

## Design

- **Cases.** A1 (24, frozen at `fa993da`) and A2 (21, fixed by the SHA-256 in
  `evals/heldout/a2_manifest.json`). The development set is not rerun; the skill was tuned
  on it.
- **Configurations and runs.** The same seven configurations, harness versions, flags,
  sandbox, and task prompts as round 2. Claude configurations run twice per case and
  condition; Codex configurations once. That is 45 cases × 2 conditions × 10 runs = 900
  outputs.
- **Layout.** `round3/runs-a1/` and `round3/runs-a2/` under the raw-run folder, mirroring
  `round2/` (`claude/<model>/<condition>/run<r>/<case>/result.txt`,
  `codex/<tag>/<condition>/<case>/output.txt`). `score_benchmark.py` picks up `round3/`
  when it exists.
- **Prompt check.** `evals/round3/check_prompts.py` must pass before scoring.
- **Judging.** A full re-judge of every held-out output in all seven conditions, in a fresh
  pass: `judge_outputs.py --sets a1,a2 --tag round3`. Judging only the new outputs would
  put them in batches without the old conditions, and batch composition is a known source
  of anchoring. The original labels are kept and compared with the new ones for the five
  original conditions (test-retest).
- **Analysis.** `evals/round3/analyze_round3.py`, unchanged after this commit except for
  bug fixes listed under Deviations. Its smoke test reproduces the report's A1 numbers.

## Primary analysis

Outcomes, aggregated as in the report (runs averaged within a configuration, seven
configurations weighted equally, judged scores averaged over the two judges):

- `a1_keep`: A1 keep cases passing the literal check;
- `a1_cleanfix`: A1 edit cases, judged clean-fix score;
- `a2_cleanfix`: A2 cases, judged clean-fix score.

Three comparisons, each on all three outcomes, give nine contrasts:

1. `compact_problems` vs `three_sentences` (Q1: does the added sentence help?)
2. `compact_problems` vs `v0.2.0` (Q1: does it close the gap?)
3. `skill_inline` vs `v0.2.0` (Q2: does delivery matter?)

Each contrast uses a two-sided exact sign test over cases, ties excluded, with Holm
adjustment across these nine. This family is fixed here; the report's 24 earlier
contrasts are not part of it.

For contrast 3, "same as the skill" is an equivalence claim, so it gets its own test: the
paired case-bootstrap 90% interval of the mean difference (5,000 resamples, seed
20261019) must lie inside ±0.10 on the outcome's 0–1 scale. With 12–21 cases this interval
may well be wider than the margin; in that case the result is reported as inconclusive,
not as equivalence.

## How results will be read

- If contrast 2 shows no clean-fix gap and contrast 1 shows a gain: the skill's advantage
  over the compact instruction is mostly its definition of a problem, and a five-sentence
  prompt is the practical recommendation.
- If contrast 2 still favors `v0.2.0`: the rest of the skill (the "ask, do not invent"
  rule, protected-element list, final check) matters beyond the problem list.
- If contrast 3 is equivalent: the Skill format adds cost (Table 6) without measured
  benefit for this task. If it is not, delivery matters, but harness differences remain a
  possible cause.
- Keep-case preservation is reported for every contrast so that a gain on edits is not
  bought with lost restraint.

Secondary and descriptive only: per-judge outcomes, per-configuration tables, invented
and damaged rates, A2 split by `judgeable_from_text`, cost and runtime, and the
test-retest agreement.

## Amendment 1, 2026-10-19, before the first round-3 run

The plan above was frozen at tag `round3-frozen`. While preparing the runners, two facts
came up: the Claude Code build used in round 2 (2.1.286) is no longer installed, and round
3 runs two weeks after round 2, during which server-side models may have changed. Comparing
round-3 outputs with round-2 outputs would mix the condition effect with that drift. This
amendment was made before any round-3 model call and supersedes the parts of the plan it
names. It is tagged `round3-frozen-2`.

- **Same-batch comparators.** Round 3 also reruns `three_sentences` and `v0.2.0` exactly as
  in round 2 (same prefix or skill installation, same task prompts). Their outputs are
  labeled `three_sentences_r3` and `v0.2.0_r3`, so they never mix with the round-2
  outputs of the same condition. Total: 45 cases × 4 conditions × 10 runs = 1,800 outputs.
- **Primary contrasts** compare round-3 conditions only:
  `compact_problems` vs `three_sentences_r3`, `compact_problems` vs `v0.2.0_r3`, and
  `skill_inline` vs `v0.2.0_r3`, each on `a1_keep`, `a1_cleanfix`, and `a2_cleanfix`.
  The family stays at nine contrasts with Holm adjustment; the equivalence check applies
  to `skill_inline` vs `v0.2.0_r3`.
- **Drift (secondary, unadjusted).** Each rerun is compared with its round-2 original on
  the same three outcomes. A large drift is reported, and it limits how round-3 numbers
  may be compared with the report's round-2 tables.
- **Judging** re-judges all nine conditions in one fresh pass.
- **Prompt check.** Prefix runs (`compact_problems`, `skill_inline`, `three_sentences`)
  must equal prefix + round-2 `no_skill` prompt; `v0.2.0` reruns must equal the round-2
  `v0.2.0` prompt.

## Not addressed here

Human validation of the judge labels is a separate study. A content-matched baseline for
v0.1.0 is not included.

## Deviations

Known before the first run (recorded with Amendment 1):

- **Claude Code build.** Round 2 used 2.1.286, which is no longer installed. Round 3 uses
  2.1.293 for every Claude run, including the reruns. All round-2 flags exist in 2.1.293.
- **Codex binary source.** Round 2 used the Codex desktop app's WSL binary; round 3 uses
  the native binary from the npm package `@openai/codex`. Both report version 0.160.0.
- **Claude working directory.** Round 2 ran every condition in one `claude-workdir` that
  contained the skills, with `--disable-slash-commands` for non-skill conditions. Round 3
  runs non-skill conditions (`compact_problems`, `skill_inline`, `three_sentences`) in an
  empty working directory, and the `v0.2.0` rerun in a working directory set up as in
  round 2.
