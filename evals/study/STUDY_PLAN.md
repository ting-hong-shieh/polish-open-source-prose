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

- **Keep set, 40**: descriptions that received no text critique and were merged.
  Expected correct behavior: leave unchanged, or at least do no harm.
- **Edit set, ~80**: descriptions a reviewer criticized for their text (not only the
  code), sampled at random from the classified pool, stratified by repository. Each case
  carries: the pre-critique title and description; the reviewer's comment verbatim; the
  diff and CI check conclusions at the comment's timestamp; the author's later revision
  (reference only, not an answer key).

**Sampling frame (2026-10-21).** The 28 repositories selected by repository rule v3
(`CASE_COLLECTION.md` step 1) together with the twelve repositories pulled first. The
twelve were chosen by hand on 2026-10-20, before any comment was read; this is stated in
the paper. Three repositories are on both lists (apache/airflow, django/django,
rust-lang/rust), so the frame has 37 repositories. One exclusion rule applies to all of
them alike: a repository is excluded if more than 25% of its pull requests created in the
window were imported from an internal review system (for example Phabricator exports
marked "Differential Revision", as in pytorch/executorch, or a Gerrit mirror, as in
golang/go), because their review does not happen on GitHub. Every repository is checked
and the result recorded. The eight domains are descriptive labels only and play no part
in sampling. Sampling is stratified by repository with a cap per repository
(`CASE_COLLECTION.md` step 5).

**Diff size rule.** Pull requests whose diff at the comment's timestamp exceeds 1,500
lines (added plus removed, from the patch) are excluded from both sets before sampling,
and the number excluded is reported. The pilot showed that a few very large diffs
dominate cost and judge load; excluding them by a rule keeps every editor and judge
looking at the whole diff. No diff is truncated for the editor.

Before freezing, the author reads every edit case's reviewer comment and records two
flags: `text_critique` (the comment criticizes the description or title, not only the
code: yes / no / uncertain) and, when yes, `fixable_from` (`code`: the diff plus CI are
enough to act on it; `partial`: acting needs a fact the review supplies that the diff
and CI do not). Cases with `text_critique` no or uncertain stay in the set and are
reported separately. The `partial` group is where `E_code` and `E1` are expected to
differ most, and is reported as its own split.

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
| `compact_check` | the compact instruction plus one sentence: "Before returning, check the description against the diff and the CI results in the working directory." (`evals/prompts/compact-check.txt`). Runs under `E_code` and `E1` only, on the edit set. **Included** (2026-10-21): in the pilot probe the diff-read rate under `E_code` rose from 0.50, 0.64, and 1.00 with `compact` to 1.00 for all three of Haiku, Sonnet, and Opus. |

The instruction conditions stand for standing configuration (a CLAUDE.md or AGENTS.md
line, or an installed skill), not for text a person types per task.

**Configurations**: Claude Haiku 5.5, Sonnet 5.5, and Opus 5.5 in Claude Code, same build
for every run, reasoning effort high. Two runs per case, condition, and configuration.
Fable 5.1 ran in the pilot and behaved like Opus 5.5 at 2.8× the cost; it is not in the
main study because of cost and because its availability has been interrupted before,
which would hinder replication. Its pilot outputs are reported in an appendix as
exploratory.

**Execution environment (2026-10-21).** Every run uses a dedicated Claude Code
configuration directory (`CLAUDE_CONFIG_DIR`) that holds no CLAUDE.md, no user skills, and
no plugins (the build's three built-in plugins are disabled, and the account's plugin and
skill sync is turned off with `syncClaudeAiPlugins` and `syncClaudeAiSkills` set to false;
without that, signing in pulled two plugins and sixteen account skills into the directory),
with auto-memory and hooks off, signed in to the author's subscription account. Runs start from a minimal process
environment (home, path, locale, and the configuration directory only) with
`--permission-mode default`. The build's own bundled skills are left as shipped; they are
listed only in the `skill` condition, where slash commands are enabled. Before the main
runs, one dry run's stream-json and `/context` output confirm that no user memory file,
user skill, plugin, or auto-memory path is in context; both are saved with the runs
(`check_clean_config.py`; a skill counts as the build's own when `/context` marks it
built-in or an empty, signed-out configuration directory lists it). First pass:
2026-10-21, `study-runs/config-check/clean-20261021T081815/`. The
pilot and rounds 2–3 ran with the author's own configuration (their global CLAUDE.md,
settings, user skills, and synced plugins); this is recorded as a deviation there.

**One harness, one prompt.** Every run uses the same English task prompt and the same
output format (`<revised>` tags, note allowed outside). This removes the round-2/3
asymmetry. Whether the editor opened `diff.patch` is read from the run logs.

**Task prompts are phrased as a developer would phrase them**, not as an editing
exercise (`evals/prompts/study-task-*.txt`, committed before freezing):
- `E0` and `E_code`: the developer asks for the description to be cleaned up before the
  pull request is posted; under `E_code` the prompt adds, neutrally, where the diff and
  CI results are.
- `E1`: the developer passes on the reviewer's comment and asks for the title and
  description to be updated in response.
The `<revised>` tags are a measurement device and are disclosed as such. These prompts
differ from the round-2/3 task prompt, so `E0` here is not directly comparable with the
earlier rounds; that is accepted, since the earlier rounds are appendix material.

**Size** (three configurations, two runs): edit 80 × 3 evidence × 3 instructions × 6 =
4,320; keep 40 × 2 × 3 × 6 = 1,440; `compact_check` 80 × 2 × 6 = 960; the effort analysis
(§6) adds 120 cases × 2 configurations × 2 instructions = 480 runs at the default effort;
7,200 outputs in all. The cost estimate is recomputed from the pilot and probe costs at
freezing.

**Rerun rule.** A run is deleted and rerun only on a harness failure: non-zero exit, no
output, or no parsable `<revised>` block. Nothing about the content of an output is a
reason to delete it; content checks only add flags. Reruns and their attempt numbers are
recorded per run.

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

GPT-6 Astra (high) and GPT-6.1 Sol (high) through Codex CLI are the main judges. A third,
cross-vendor judge is Gemini, through the Gemini API: Gemini 3.1 Pro or Gemini 3.8 Flash,
chosen before freezing by its agreement with Astra (Sol for reference) on a fixed sample
of 100 pilot outputs (`judge_compare_sample.py`, seed 20261021; strata evidence level ×
editing model, 8 or 9 outputs per stratum, 5 or 6 per case, all 19 judged pilot cases),
judged with the same prompt, labels, and per-case batches. For cost the author prefers
Gemini 3.8 Flash (2026-10-21); 3.1 Pro is run only if Flash's agreement with Astra turns
out unacceptable. The Gemini judge goes through the Gemini Batch API (half the standard
price, results within 24 hours) with the same request body as a direct call. The Gemini judge runs at thinking
level high with the API's default sampling and always receives the diff inline (same
truncation rule); the model id and the model version the API reports are recorded per call. GPT-6 Luna was tried in the pilot and is not used: on the 1,368 pilot outputs
its scale differed from the other two (addressed 0.5 for 37% of outputs against 24–25%,
damaged 14% against 22%), and its κ with them on complete clean fix was 0.43–0.46. Astra
and Sol agreed closely (κ 0.865 on complete clean fix; all five labels equal on 1,142 of
1,368 outputs), so they count as two judges from one vendor, and the Gemini judge is the
cross-vendor check. None is a tested model. Outputs for one case are shuffled under
random labels and judged in batches; batches shrink to 5 for diffs over 1,000 lines.

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

`compact_check` is included, so one contrast is added to this family (five in all):
5. `compact_check − compact` on the complete-clean-fix rate under `E_code`, with the
   diff-read rate reported beside it.

**Effort analysis (secondary, 2026-10-21).** Haiku and Sonnet under `E_code` with `none`
and `compact`, at the build's default reasoning effort (medium in Claude Code 2.1.293,
passed explicitly) and at high, one run per case, keep and edit sets. The high-effort
runs are run 1 of the same arms in the main study; the default-effort runs are added.
Outcomes: diff-read rate (both sets), unchanged rate (keep set), complete clean fix
(edit set, judged). Contrast: default − high per configuration and instruction, with
paired case-bootstrap 95% intervals. It is reported as a secondary analysis outside the
Holm families. The pilot probe (low and medium effort) stays in the appendix.

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

## 7b. Scope and known limits (to state in the paper)

- The task isolates one step, revising an existing description. The most realistic
  agent workflow writes the description from the diff in the first place; that
  generation task is out of scope and named as future work.
- Claims are scoped to "when an agent is asked to revise a pull request description",
  with standing instructions as configuration, in Claude Code with Claude models.
  Rounds 2–3 supply cross-harness evidence for the restraint pattern in an appendix.
- Reasoning effort is high in the main comparisons; the effort analysis (§6) reports
  Haiku and Sonnet at the default setting.
- Two judges are from one vendor and agree closely; the third is from another vendor.
  The author's blind check is the only validity evidence.

## 8. Order of work

1. **Pilot** (`PILOT_PLAN.md`): the 21 A2 cases, all evidence levels and instruction
   conditions, four configurations, three candidate judges. Purpose: verify the new
   mechanics (evidence files, diff-read logging, judging with diffs, Fable behavior,
   judge stability), estimate cost. Pilot results do not enter the primary analysis.
   Two pilot probes decide two pre-freeze choices: (a) `compact_check` on `E_code`, three
   configurations, two runs (126 runs): included in the study if it moves the diff-read
   or unchanged rate; (b) reasoning effort default and low for Haiku and Sonnet on
   `E_code` under `none` and `compact`, one run (84 runs): appendix only, to show how
   diligence changes at the settings people actually use. After these two probes no
   further conditions are added. Both probes use the pilot's prompts (round-3 task
   prompt with the pilot's evidence paragraph), so that they compare with the pilot's
   `E_code` runs of the same arms; probe (b) is 21 cases × 2 configurations × 2
   instructions × 2 effort levels = 168 runs (the default level in Claude Code 2.1.293
   is medium for both models, passed explicitly as `--effort medium`). Neither probe is
   judged; they report the diff-read and unchanged rates only.
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
models; the judges are two OpenAI models and one Google model; the cases are real text
sampled by a fixed
procedure and flagged by the author; the human check is the author's own blind rating.
All of this is stated in the paper.

## Changes before freezing

- 2026-10-20: first draft, replacing the round-4 plan.
- 2026-10-20: flag split into `text_critique` and `fixable_from`; pilot flags recorded in `flags.json`.
- 2026-10-21, after the pilot runs: Fable dropped from the main study; diff-size
  sampling rule (≤ 1,500 lines) instead of truncation; rerun rule limited to harness
  failures; `compact_check` added as a conditional fourth instruction condition with a
  pilot probe; effort probe for the appendix; task prompts rephrased as developer
  requests; keep set 40; scope section 7b added.
- 2026-10-21, author's decisions on the pilot: Fable's pilot outputs go to an appendix
  as exploratory; the diff-size rule is written into `CASE_COLLECTION.md` step 5 with
  the share excluded from the pool; the 72 pilot runs kept from attempt 5 carry a flag;
  the low diff-read rate of Haiku and Sonnet under `compact` × `E_code` is reported as a
  result and the task prompt is not changed for it; the effort probe's size is 168 runs
  (the earlier figure, 84, covers one effort level only).
- 2026-10-21, author's decisions after the probes and the pilot judging:
  - sampling frame: rule v3's 28 repositories ∪ the twelve pulled first (37; the twelve
    were picked before any comment was read); a repository is excluded when more than
    25% of its pull requests in the window were imported from an internal review
    system; domains are labels only; sampling stratified by repository with a cap per
    repository;
  - `compact_check` included under `E_code` and `E1` (probe: diff-read rate 1.00 for all
    three configurations);
  - judges: Astra and Sol as the main judges, a Gemini judge (3.1 Pro or 3.8 Flash,
    chosen by agreement with Astra on 100 pilot outputs) as the cross-vendor third;
    Luna dropped;
  - AI-written review comments and templated comments are excluded from the case pool
    (`CASE_COLLECTION.md` step 4);
  - runs use a dedicated configuration directory without the author's CLAUDE.md,
    plugins, user skills, or auto-memory (§4, Execution environment);
  - the effort comparison becomes a secondary analysis at default and high effort
    (§6); size now 7,200 outputs;
  - keep set target corrected from "~30" to 40 in §3, matching the earlier entry.
  - Gemini judge: the author prefers 3.8 Flash for cost and asked for the Batch API;
    `judge_pilot.py --gemini-batch` sends the requests as batch jobs (2026-10-21).

## Deviations

None yet.
