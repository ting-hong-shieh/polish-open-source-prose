# Round 4: revising a criticized description with the review and the code in hand

Draft. To be frozen (committed and tagged `round4-frozen`) before any round-4 model run.
Any change after the first run goes under "Deviations" with the date and the reason.

## Question

Rounds 2 and 3 gave the editor only the pre-critique title and description of 21 real
pull requests (A2). Every condition fixed little (clean-fix 0.10–0.25), and in 12 of the
21 cases the reviewer's point depended on something outside the text. The editor could at
best ask the author, and no author was there to answer.

Round 4 changes the task to the situation an agent is actually in after review: it made
the change, a reviewer objected to the description, and it must revise the description.
The editor receives the reviewer's comment, the diff of the change as it stood when the
reviewer commented, and the CI conclusions for that commit.

- **Q1, evidence.** With the review and the code available, how much more of the
  reviewer's point gets fixed, and does fixing it come with more invented facts or
  damaged text?
- **Q2, code without the review.** Given the code but not the review, does the editor
  find and fix the mismatch on its own? This is the rounds-2/3 task with the missing
  evidence supplied, and it answers the report's own limitation that editors "do not
  receive the external evidence that many reviewers ask for".
- **Q3, instructions under evidence.** Once the evidence is there, does the skill still
  differ from a short instruction or from no instruction?

The paper reports the three evidence levels as three tasks: polish blind (E0), polish
with the code (E_code), revise after review (E1).

## Cases

The same 21 A2 cases, fixed by the SHA-256 in `evals/heldout/a2_manifest.json`. For each
case the private data folder adds:

- `review.md`: the reviewer's comment verbatim (the earliest comment criticizing the
  text, with its timestamp and URL);
- `diff.patch`: the three-dot diff of the pull request head at that timestamp against
  its base, from `a2-commit-feasibility` (all 21 heads were recoverable);
- `ci.md`: the check-run names and conclusions for that head commit (success, failure,
  skipped, cancelled); job logs are no longer available and are not used.

Before freezing, the author reads each case's `review.md` and confirms one flag per
case: the comment criticizes the description or title (not only the code) and the
diff plus CI are enough to act on it. Cases failing the flag stay in the set but are
reported separately. The flags are committed with the plan.

## Arms

Three evidence levels × four instruction conditions = 12 arms.

| Evidence | What the editor receives |
| --- | --- |
| `E0` text only | the round-2/3 task prompt, unchanged (same-batch rerun) |
| `E_code` code, no review | the same task prompt, plus one neutral paragraph saying that `diff.patch` in the working directory holds the change and giving the CI conclusions; it does not mention a reviewer and does not ask the editor to check anything (`evals/prompts/round4-code-paragraph.txt`) |
| `E1` review + code | the same task prompt, plus one paragraph giving the reviewer's comment and the CI conclusions verbatim, and saying that `diff.patch` in the working directory holds the change (`evals/prompts/round4-evidence-paragraph.txt`) |

The `E_code` paragraph is deliberately minimal. Any wording that tells the editor to
compare the description with the code would turn `E_code` into a hint condition; the
wording is fixed here and its influence is a disclosed limitation.

| Instruction | As in round 3 |
| --- | --- |
| `no_skill` | task prompt alone |
| `three_sentences` | compact instruction prefix |
| `v0.2.0` | skill installed and forced, as in rounds 2–3 |
| `skill_inline` | skill text prefix |

The diff is a file, not prompt text, so the run logs show whether the editor read it.
`review.md` and `ci.md` are also placed in the working directory. E1 arms use the same
clean or skill working directories as round 3 with these files added; E0 arms are the
round-3 layout unchanged. The E1 paragraph is the same for every instruction condition
and is committed with the plan (`evals/prompts/round4-evidence-paragraph.txt`).

Seven configurations as before; Claude configurations run twice, Codex once:
21 × 12 × 10 = 2,520 outputs. The E0 arms exist from round 3 (and round 2 for
`no_skill`); they are rerun so that every contrast is within one batch, as in round 3.

**Did the editor read the diff?** For `E_code` and `E1`, each run records whether
`diff.patch` was opened (Claude `meta.json` reads; Codex events). Nothing forces the
read. The read rate is a result in its own right, and every `E_code` and `E1` outcome
is also reported split by read / not read.

## Judging

A fresh pass over all 2,520 outputs by both judges (Opus 5.5, GPT-6.1 Sol), labels
masked and shuffled per case as before. Whatever the editor saw, the judge always sees:

- the original title and description;
- the reviewer's comment verbatim (replacing the drafted critique summary);
- `ci.md` and `diff.patch`;
- a uniform must-not list: do not delete or alter a disclosure line, a license header,
  an identifier, or the scope of the change; do not state anything the diff, CI, or
  original text does not support;
- the revised text and any note to the author.

Judge questions are unchanged: addressed (0 / 0.5 / 1) against the reviewer's comment,
invented, damaged. For the four cases whose diff exceeds 1,000 lines, the judge batch is
5 outputs instead of 20, and the diff is passed whole.

## Primary analysis

Aggregation as in the report: runs averaged within a configuration, seven
configurations equal weight, judges averaged. Outcome: A2 clean-fix.

**One primary contrast:** `E1` minus `E0`, pooled over the four instruction conditions,
on clean-fix. Test: paired case-bootstrap 95% interval of the mean difference (5,000
resamples, seed 20261020), with the two-sided exact sign test as a robustness check.
Power: from round-3 A2 intervals the per-case SD of a paired difference is about 0.10–
0.12; with 21 cases a difference of about 0.08–0.10 is detectable at 80% power. The
expected effect is larger than that if evidence helps at all.

**Secondary (one family of four, Holm-adjusted), all on clean-fix pooled over the
four instruction conditions unless stated:**
1. `E_code − E0` (does the code alone help?);
2. `E1 − E_code` (what does the review add beyond the code?);
3. `E1 − E0` on the damaged rate (does fixing cost accuracy?);
4. under `E1`: `v0.2.0` vs `no_skill` on clean-fix (does the skill still matter?).

Descriptive only: the remaining instruction contrasts under `E1` and `E_code`,
invented and unchanged rates, per judge, per harness, split by the author's flag, split
by whether `diff.patch` was read, cost and tokens.

## How results will be read

- A large, significant primary effect with no rise in invented or damaged rates: the
  rounds-2/3 ceiling was the missing evidence, not the editors; the paper's A2 claim
  becomes "editors fix what they are told about when they can see the code".
- A large primary effect with higher invented or damaged rates: evidence raises
  correction at a cost; report the trade-off.
- A small or non-significant primary effect: even told and shown, the editors do not
  fix the description; the problem is correction itself.
- `E_code` close to `E0` with a low diff read rate: given the code, the editors do not
  look at it unless told there is a problem; report this as a finding about
  self-checking, not as a failure of the design.
- `E_code` close to `E0` with a high read rate: the editors read the code and still do
  not notice the mismatch; the correction problem is not only missing evidence.
- `E_code` well above `E0`: the rounds-2/3 ceiling was mostly the missing code.
- If the `v0.2.0` vs `no_skill` contrast under `E1` is near zero: with evidence,
  instructions stop mattering for correction; report whether they still matter for
  restraint (unchanged, damaged).

## Not addressed here

Pre-emptive detection (the rounds-2/3 task), more cases, and human validation at scale.
Whether to collect more real cases is decided after this round, as a separate
preregistered round, not by extending this one.

## Deviations

None yet.
