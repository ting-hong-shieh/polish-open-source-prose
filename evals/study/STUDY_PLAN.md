# Study plan: restraint, correction, and evidence when coding agents edit pull request descriptions

Status: **draft**. This plan supersedes the round-4 plan (now `PILOT_PLAN.md`, kept as the
pipeline pilot) and reorganizes the project around real English pull request descriptions.
It is frozen (tagged `study-frozen`) only after the pilot has run and the sampled case set
is fixed; until then it may change, and every change is recorded in "Changes before
freezing" at the end. After freezing, changes go under "Deviations".

## 1. Question

When a coding agent edits a pull request description, when does it damage text that was
fine, when does it fix text that was wrong, and how do instructions and evidence change
each of these?

1. **Restraint.** On descriptions nobody criticized, does the agent change them, and does
   an instruction stop it?
2. **Correction from text alone.** On descriptions a reviewer criticized, how much does the
   agent fix with only the text?
3. **Evidence.** Given the diff and CI results, does the agent check the description
   against the code on its own? Given the reviewer's comment as well, does it fix the
   description correctly?
4. **Instructions under evidence.** Once the evidence is there, does the skill still differ
   from a short instruction or from none?

Motivation to state in the paper: whether a pull request is opened by a person or by an
agent, the description is where the author's claims meet the reviewer. Agent-authored
pull requests whose descriptions do not match the code are accepted far less often
(Gong et al.); responding to a reviewer's objection by revising the description is a
step every agent-driven pull request workflow contains. The task is not "polishing for
a person"; it is the description step of that workflow.

## 2. What is dropped from earlier rounds, and why

- **Chinese cases**: all real data is English; the judges' competence in Chinese is
  untested; the post-hoc round-3 split showed the Chinese cases driving one result.
- **Constructed cases (A1)**: drafted by Claude, rubrics shared the skill author's view,
  and the paper then has to defend them. They stay in the repository as the skill's
  regression tests.
- **Development set**: the skill was tuned on it; mentioned once in the method.
- **Skill v0.1.0**: the author's version history, not a condition the questions need.
- **Compact + problems** and **skill text inline**: answered in round 3 (Appendix in the
  paper). Inline may be rerun on E0 only if budget remains after the main runs.
- **Codex configurations**: dropped to remove the harness asymmetry. Rounds 2–3 showed the
  same qualitative pattern in Codex; that goes in an appendix as cross-harness evidence.

## 3. Cases

All cases are real, English, public pull requests. See `CASE_COLLECTION.md` for the
sampling procedure. Target sizes:

- **Keep set, ~30**: descriptions that received no text critique and were merged.
  Expected correct behavior: leave unchanged, or at least do no harm.
- **Edit set, ~80**: descriptions a reviewer criticized for their text (not only the
  code), sampled at random from the classified pool, stratified by repository. Each case
  carries: the pre-critique title and description; the reviewer's comment verbatim; the
  diff and CI check conclusions at the comment's timestamp; the author's later revision
  (reference only, not an answer key).

Before freezing, the author reads every edit case's reviewer comment and records one flag:
the comment criticizes the description or title, and the diff plus CI are enough to act
on it. Cases failing the flag stay in the set and are reported separately.

The 21 existing A2 cases join the edit set if they pass the same flag; the pilot runs on
them first.

## 4. Conditions

**Evidence levels**

| Level | Editor receives | Sets |
| --- | --- | --- |
| `E0` | the title and description only | keep, edit |
| `E_code` | plus `diff.patch` in the working directory and the CI conclusions, in a neutral paragraph that does not mention a review or ask for a check | keep, edit |
| `E1` | plus the reviewer's comment verbatim | edit |

**Instruction conditions**

| Condition | Content |
| --- | --- |
| `none` | task prompt alone |
| `compact` | the four-sentence instruction, prepended |
| `skill` | polish-open-source-prose v0.2.0, loaded through the Claude Code Skill mechanism and forced, as in rounds 2–3 |

**Configurations**: Claude Haiku 5.5, Sonnet 5.5, Opus 5.5, and Fable 5.1 in Claude Code,
same build for every run, reasoning effort high (or the model's default where high is
unavailable; recorded). Fable stays only if the pilot shows normal behavior and
acceptable cost. Two runs per case, condition, and configuration.

**One harness, one prompt.** Every run uses the same English task prompt and the same
output format (`<revised>` tags, note allowed outside). This removes the round-2/3
asymmetry. Whether the editor opened `diff.patch` is read from the run logs.

**Size**: edit 80 × 3 × 3 × 4 × 2 = 5,760; keep 30 × 2 × 3 × 4 × 2 = 1,440; about 7,200
outputs. Budget estimate: USD 300–500 depending on Fable pricing; confirmed after the
pilot.

## 5. Scoring

### Keep set

- **Unchanged** (mechanical): equal to the input after normalization (Unicode NFC,
  CRLF→LF, trailing whitespace per line and surrounding whitespace removed).
- **Edit ratio** (mechanical): character-level Levenshtein distance between normalized
  output and input, divided by input length.
- **Harmful** (judged): the change altered a fact, condition, scope, identifier,
  license or disclosure text, or the author's voice, or added unsupported content.

### Edit set (judged; the judge always sees the original, the reviewer's comment, the
diff, the CI conclusions, the revised text, and any note, whatever the editor saw)

| Label | Question | Values |
| --- | --- | --- |
| addressed | does the **revised text** resolve the reviewer's point? (questions in a note do not count here) | 0 / 0.5 / 1 |
| code-consistent | does the revised text contradict the diff or CI anywhere? | yes / no |
| invented | does the revised text state something that neither the original, the diff, nor the CI supports? (facts taken from the diff are **not** invented) | yes / no |
| damaged | was something correct and needed removed or altered? | yes / no |
| asked | did a note ask the author something, and was it a question the evidence could not answer? | none / answerable / unanswerable |

**Primary outcome: complete clean fix** = addressed is 1, code-consistent, not invented,
not damaged. A binary per output; reported as a rate.

Secondary: mean clean-fix (addressed × (1 − invented) × (1 − damaged)), kept for
comparability with rounds 2–3; each label separately; the ordered scale
harmful < unchanged < partial < complete clean fix, as a descriptive view of restraint
and correction on one axis.

### Judges

GPT-6 Astra (high) and GPT-6.1 Sol (high) through Codex CLI, with GPT-6 Luna as a third
if the pilot shows it stable. None is a tested model. Outputs for one case are shuffled
under random labels and judged in batches; batches shrink to 5 for diffs over 1,000
lines. All judges are from one vendor; this is stated as a limitation, and a
cross-vendor judge (Gemini) is the first addition if reviewers or the pilot call for it.

### Human check

The author blind-rates a stratified sample of about 100 edit outputs and 40 keep outputs
against the same labels, in a package that hides model and condition. Agreement with
each judge (κ) is reported. This is the only evidence on judge validity, as opposed to
judge consistency.

## 6. Analysis

Unit: the case. Runs are averaged within a configuration; the four configurations get
equal weight (also reported per configuration).

**Primary hypothesis (one):** `E1 − E0` on the complete-clean-fix rate, edit set, pooled
over the three instruction conditions. Paired case-bootstrap 95% interval of the mean
difference (5,000 resamples, seed fixed at freezing); exact sign test as robustness.
Power: with 80 cases a difference of about 0.05–0.07 in the rate is detectable at 80%
power under the per-case variability seen in round 3.

**Secondary family (Holm-adjusted, four contrasts):**
1. `E_code − E0`, complete clean fix (does the code alone help?);
2. `E1 − E_code`, complete clean fix (what the review adds);
3. `E1 − E0`, damaged rate (does fixing cost accuracy?);
4. under `E1`, `skill − none`, complete clean fix (does the skill still matter?).

**Restraint family (Holm-adjusted, three contrasts, keep set):** `compact − none` and
`skill − none` on the unchanged rate under `E0`; `E_code − E0` on the unchanged rate
pooled over instructions (does seeing the code make the editor touch fine text?).

Everything else is descriptive: per configuration, per judge, by whether `diff.patch`
was read, by reviewer-critique type, by the author's flag, edit ratios, cost and tokens.

## 7. How results will be read

- `E1` far above `E0`, damage flat: the text-only ceiling was missing evidence; told and
  shown, the editors fix descriptions.
- `E1` far above `E0`, damage up: evidence buys correction at a cost; report the trade.
- `E1` near `E0`: even told and shown, the editors do not fix the description; the
  problem is correction itself, not evidence.
- `E_code` near `E0` with a low diff-read rate: given the code, editors do not look
  unless told there is a problem.
- `E_code` near `E0` with a high read rate: editors read the code and still miss the
  mismatch.
- `skill − none` under `E1` near zero: with evidence, instructions stop mattering for
  correction; report whether they still matter for restraint.
- Keep set: `E_code` lowering the unchanged rate means that showing the code invites
  edits to text that was fine; whether those edits are harmful decides how to read it.

## 8. Order of work

1. **Pilot** (`PILOT_PLAN.md`): the 21 A2 cases, all evidence levels and instruction
   conditions, four configurations, three candidate judges. Purpose: verify the new
   mechanics (evidence files, diff-read logging, judging with diffs, Fable behavior,
   judge stability), estimate cost. Pilot results do not enter the primary analysis.
2. **Collection** in parallel (`CASE_COLLECTION.md`); author spot-checks the classifier
   and flags the sampled cases.
3. **Freeze**: sampled sets by hash, this plan, prompts, judge prompt, seeds; tag
   `study-frozen`.
4. **Run, judge, human check, analyze.**
5. **Paper**: written around this study; rounds 2–3 as an appendix (constructed-case and
   cross-harness evidence) and as the source of the inline and problem-list results.

## 9. Disclosure

The skill under test was written with Claude; the plan, scripts, and prompts were
drafted by Claude sessions under the author's direction; the editing models are Claude
models; the judges are OpenAI models; the cases are real text sampled by a fixed
procedure and flagged by the author; the human check is the author's own blind rating.
All of this is stated in the paper.

## Changes before freezing

- 2026-10-20: first draft, replacing the round-4 plan.

## Deviations

None yet.
