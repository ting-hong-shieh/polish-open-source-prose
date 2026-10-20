# Collecting more real cases (for a later round, not round 4)

Round 4 runs on the existing 21 A2 cases. In parallel, and without touching round 4, we
build a larger candidate pool so that a later round can sample real cases randomly
instead of by keyword. Nothing here involves running an editing model.

## Population

Pull requests whose title or description was criticized in review. "Representative"
means a random sample of that population, not of all pull requests.

## Procedure

1. **Repositories.** 12–20 large, active open-source repositories across languages and
   ecosystems, chosen before looking at any comment (for example: the four already
   used, plus kubernetes/kubernetes, rust-lang/rust, pandas-dev/pandas, numpy/numpy,
   pytorch/pytorch, nodejs/node, golang/go, home-assistant/core, grafana/grafana,
   apache/spark, elastic/elasticsearch, django/django). Record the final list and why.
2. **Period.** A fixed window, for example 2026-01-01 to 2026-09-30.
3. **Pull everything.** All review comments and issue comments on pull requests in
   the window (GraphQL), with the pull request's title/description edit history. Save
   raw under `$POLISH_EVAL_DATA/Raw/`. Report the count before any filtering.
4. **Classify.** Two passes:
   - a cheap keyword pass (description, title, "does not match", "AI-generated",
     "evidence", "claim", "misleading", "please update the description", …) to cut
     the volume;
   - an LLM pass on the survivors with one question: does this comment criticize the
     pull request's title or description text (not only the code)? Output yes/no and
     the quoted sentence. Use one model, fixed prompt, committed before running.
   - The author spot-checks a random 50 positives and 50 negatives and reports
     precision and recall of the classifier. These numbers go in the paper.
5. **Sample.** From the positives, a random sample (seed fixed in advance), stratified
   by repository so no single project dominates. Target 60–100, plus 20–40 uncriticized
   merged pull requests from the same repositories and window as keep cases.
6. **Per case**, collect what round 4 collects: pre-critique title/description, the
   reviewer comment verbatim, the diff at the comment's timestamp, CI conclusions, and
   the author's later revision. Record cases where the head commit cannot be recovered.
7. **Freeze** the sampled set by URL and SHA-256 before any editing model runs on it,
   as for A2.

## What to report back before sampling

Counts per repository: pull requests in the window, comments pulled, keyword
survivors, LLM positives, spot-check precision/recall. The author decides the sample
size and whether to proceed from those numbers.

## Costs

GitHub API only, plus one classifier call per keyword survivor. Estimate the classifier
volume from the survivor count before running it.
