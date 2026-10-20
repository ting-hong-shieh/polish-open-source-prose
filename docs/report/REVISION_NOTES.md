# Revision notes for the report

These notes come from a review of the 2026-10-19 preprint candidate
(`Leave_Clear_Text_Alone_2026-10-19_preprint_candidate.pdf`). They are input for the next
revision, not decisions: the author approves the outline before any text changes.

## 0. Before editing

- **Edit the right source.** `docs/report/report.tex` in this repository is older than the
  preprint candidate: it still says "Three sentences", and it has no record-level audit,
  no Appendix B, and no parser correction. Edit the 2026-10-19 source instead:
  `Leave_Clear_Text_Alone_2026-10-19_arXiv_source.zip` (135,922 bytes, SHA-256
  `4fa36342bcffa81128391c8d684ef035370cd17f421e827937cc22e8c506675a`), which holds
  `main.tex`, `figures/`, and `tables/`. The author keeps it outside Git, under
  `$POLISH_EVAL_DATA/Exports/polish-open-source-prose/` (next to
  `eval-runs-2026-10-04/`). Check the
  hash before editing; if the file is missing or the hash differs, stop and ask. Do not
  rebuild the candidate from the old file. Older drafts (2026-10-16, 2026-10-18) are history
  only.
- **The 2026-10-18 public patch overlaps this branch.** An earlier revision prepared
  `Leave_Clear_Text_Alone_repository_public_patch_2026-10-18.zip` with the A1 parser
  correction. This branch fixes the same parser in `evals/score_benchmark.py`. Do not apply
  both; compare them and keep one.
- **Other inputs from that revision**, in the same folder if the author copied them: a
  prior-art review, a simulated peer review, and a submission checklist (all in
  Traditional Chinese). They are AI reviews, not external peer review.
- **Numbers come from files, never from memory.** Every number about round 3 comes from
  `evals/results/round3-analysis.json`. Every number already in the paper stays as it is
  unless a script reproduces a different value, and then the change is reported to the
  author.
- **Process.** First send the author a revision outline (section by section: what changes
  and why). Edit only after approval. After editing, a fresh session that has not seen the
  editing reviews the compiled PDF against these notes.

## 1. The claim

State the paper's point in one sentence and build the abstract, introduction, and
conclusion around it. A candidate:

> Telling a coding agent to change less is easy; getting it to change the right things is
> hard, and the two have to be measured separately.

The preservation result alone is thin: a four-sentence prompt already gets most of it.
The more interesting findings are the trade-off between restraint and correction, and the
Appendix C pattern in which the editor's note names the problem while the revised text
keeps it. Move that pattern into the main results.

The title can stay, but consider one that names the trade-off rather than only
preservation. This is the author's call.

## 2. Integrating round 3

`evals/round3/PLAN.md` fixes how results are read. Follow it:

- Report the nine primary contrasts with the Holm adjustment specified there, as a new
  subsection, and update RQ2 and RQ3 accordingly.
- `skill_inline` vs `v0.2.0` is called equivalent only if the 90% interval lies within
  ±0.10; otherwise it is inconclusive. Do not write "no difference" from a non-significant
  test.
- Report the test-retest agreement between the original and round-3 judge labels in the
  judge-agreement section.
- Update the Discussion and Threats sections: the "content-matched baseline" limitation is
  now partly addressed; human validation is still missing.
- If round 3 overturns an earlier interpretation (for example, the problem list closes the
  gap), say so plainly rather than softening it.

### How the round-3 results read (2026-10-20)

Take every number from `evals/results/round3-analysis.json` (primary, drift, retest) and
`evals/results/round3-secondary.json` (post-hoc tables). The readings below follow
`PLAN.md`; they are not numbers to copy.

- **Q1 (content).** Adding the problem-definition sentence did not close the gap: against
  `v0.2.0_r3` it loses on A1 clean-fix in every non-tied case, the only primary contrast
  significant after Holm. Against `three_sentences_r3` it is directionally better on both
  clean-fix outcomes but not significant. The original Discussion guessed that naming the
  problems was the skill's active ingredient; round 3 does not support that. Say so, and
  say that the rest of v0.2.0 (ask instead of inventing, the protected-element list, the
  final check) matters beyond the problem list, without claiming which part.
- **Q2 (delivery).** A2 clean-fix meets the pre-registered equivalence margin. A1 is
  inconclusive under the plan: inline preserved more and corrected slightly less, with
  90% bootstrap intervals that exclude zero (the 95% interval for A1 keep touches zero)
  but sign tests that are not significant. Report
  this as a descriptive direction that fits the paper's trade-off framing, not as a
  finding.
- **Post-hoc, label as exploratory.** The inline keep advantage comes almost entirely
  from the four Traditional Chinese keep cases, and its clean-fix deficit from English
  edit cases. One candidate explanation was checked and ruled out: the Skill runs read
  the zh-Hant-TW locale reference in every Chinese case, in all seven configurations
  (`round3-secondary.json`), so the difference is not that the Skill skipped the file.
  The mechanism is unknown; say so, and do not offer an untested explanation as a
  finding. On A1 clean-fix the
  problem-definition sentence raised the mean in five configurations, left Opus 5.5
  unchanged, and lowered Sonnet 5.5 slightly, so the heterogeneity Karpo & Chernodub report for GEC did not
  appear strongly here.
- **Drift.** The reruns match their round-2 originals closely, so round-3 and round-2
  tables can be read side by side. State this once in the method.
- **Judge reliability.** Re-judging gave very high agreement on "addressed" and moderate
  agreement on invented, damaged, and keep-case harm (lowest for the Sol judge on harm).
  This is test-retest reliability, not validity: it shows the judges are consistent, not
  that they are right. Human validation remains the main open limitation; the claim
  strength the paper relies on (hedges and overclaims) is exactly what Chen et al.
  (arXiv:2608.24419) find LLM judges least sensitive to.
- **Run history to disclose.** Claude Code 2.1.293 instead of 2.1.286; gpt-6-luna
  rate-limit retries; four parser changes, all correct parses; one Claude judge chunk on
  A2 completed by judging a single output on its own; orchestration by a Claude Fable 5.1
  session. All are in `PLAN.md` Deviations and the run folder's `versions.txt`.

## 3. Weaknesses a reviewer will raise

Address each in the text where it applies; do not just add a caveat.

1. **A1 favors the skill by construction.** A1 was drafted by Opus 5.5, its rubrics share
   the skill author's idea of a good edit, and v0.2.0's rules target the same critique
   types. Say this where A1 results are first reported, and give A2 at least equal weight.
   On A2, v0.2.0 vs no instruction is 10:7 (p = 0.63) and it trails v0.1.0 descriptively.
2. **No human validation.** Both judges are tested models. Keep this prominent. A small
   human study (about 100 A2 outputs, two raters) is the next step; mention it as such.
3. **Harness asymmetry.** Claude outputs can carry a note to the author that earns
   "addressed" credit; Codex outputs cannot, and Codex received a Chinese task prompt even
   for English cases. Say how this affects A2 addressed scores in particular.

## 4. Text that reads like a revision memo

The paper must read as a paper, not as a log of its own revision. Rewrite or move to an
appendix every passage that talks about the draft, the revision, or unreleased artifacts.
Examples from the candidate:

- "accompany this manuscript draft"
- "This revision recomputes ..." (Appendix B)
- "Values are transcribed from the original generated table." (Tables 1 and 2)
- "The published repository still contains the historical pre-correction records until an
  explicit new artifact version is released"
- "the associated proposed patch ... is not silently applied to GitHub"
- "No new benchmark generations, new judge calls, or human ratings were produced in this
  revision." (Use of AI tools)

Release the corrected artifacts first (round 3's scoring run already applies the parser
fix), then describe the final state once. The record-level audit becomes a short paragraph
in the evaluation section plus an appendix.

## 5. Specific errors

- **Broken sentence** in "Judged scoring": "... an identifier, or the author's both judges
  are also tested models" is missing text. It should end the harm list with "or the
  author's voice." and start a new sentence "Both judges are also tested models, so we
  report them separately ...".
- **Figure 2 caption** refers to "the labels 49 and 24", but the panels now say "19 keep
  cases" and "12 keep cases". Remove the leftover clause.
- **Section 7, "What the skill does not do"**: "No condition reached a mean clean-fix score
  above 0.25 on those critiques" reads as if it refers to the critiques needing outside
  facts, but 0.25 is the maximum over all A2 cases. Either compute the value for that
  subset or reword.

## 5a. Four A2 inputs were not the version the reviewer saw (found 2026-10-20)

`evals/study/check_a2_snapshots.py` compares each A2 input with the title and
description as they stood just before the quoted reviewer comment. Four of 21 cases
differ (arrow 49771, arrow 50377, cpython 143246, cpython 150425): the case builder had
used the description before the first prose-related comment in the thread, and the
quoted comment came later, after an edit. Rounds 2 and 3 ran on those inputs. The paper
must say this where A2 is described and in Threats: for four cases the editor revised,
and the judges graded against a critique of, a version of the description the reviewer
had not seen; the A2 results are reported as run; the case file is corrected (version 2,
new manifest hash) for the study. Do not recompute round-2/3 numbers on the corrected
file; that would be a new run.

## 6. Hedging

Nearly every result is followed by its own disclaimer ("This is not evidence of
equivalence", "These are exploratory", "not a complete-correction rate"). A paper about
over-editing reads over-edited. Keep each caveat once, where it matters most, and collect
the rest in Threats to Validity. The abstract should carry at most two caveats: LLM judges
instead of humans, and a small, selected A2 sample.

## 7. Venue

At its current size the paper fits an arXiv preprint plus a software-engineering or
LLM-agent workshop. Round 3 and a small human study are what a main-track submission
would need. The author decides the target; write for it once decided.
