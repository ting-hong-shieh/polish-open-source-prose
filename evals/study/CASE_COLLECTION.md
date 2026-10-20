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

   **Final list (2026-10-20), fixed before reading any comment:** apache/airflow,
   apache/datafusion, apache/arrow, python/cpython, kubernetes/kubernetes, rust-lang/rust,
   pandas-dev/pandas, numpy/numpy, nodejs/node, prometheus/prometheus, apache/spark,
   django/django. Pull request counts in the window (search API, 2026-10-20): airflow
   11,867; cpython 10,324; rust 9,688; spark 5,339; kubernetes 4,967; datafusion 4,382;
   nodejs 3,955; pandas 3,582; numpy 1,861; prometheus 1,758; django 1,560; arrow 1,424;
   about 60,700 in all. Four candidates from the example list were left out for volume
   alone, before any comment was read: pytorch/pytorch (22,193), home-assistant/core
   (15,530), elastic/elasticsearch (14,826), grafana/grafana (14,654) together exceed the
   twelve kept; they can be added as a separate pull if the sample needs them. golang/go
   (600) was on the first list and replaced by prometheus/prometheus after one test pull
   showed that its pull requests are mirrored to Gerrit for review and carry only bot
   comments on GitHub; the replacement keeps a Go project in the list.
2. **Period.** A fixed window, for example 2026-01-01 to 2026-09-30.

   **Fixed window:** 2026-01-01 to 2026-09-30, by pull request creation date.
3. **Pull everything.** All review comments and issue comments on pull requests in
   the window (GraphQL), with the pull request's title/description edit history. Save
   raw under `$POLISH_EVAL_DATA/Raw/`. Report the count before any filtering.

   Script: `evals/study/collect_pr_comments.py`. Pull requests come from the GraphQL
   `pullRequests` connection (newest first, stopped below the window) with review
   summaries and per-request comment and thread counts; comments are then fetched per
   pull request in batched GraphQL queries sized by those counts. A first version used
   the repository-wide REST comment listings and was dropped: their `since` parameter
   filters by update time, so pages fill with old comments that bots re-edited and the
   cursor stalls (apache/airflow stopped at 2026-03-12). The edit history is stored as
   the edit count per pull request; the edits themselves are fetched later only for
   sampled cases.
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

   **Rule (2026-10-20):** one timestamp per case, the selected reviewer comment's, fixes
   everything: the title and description are the last version edited before it (body
   edit history and title renames), the diff is the pull request head at that time, and
   the CI conclusions are that head's. The A2 set had four cases whose description came
   from an earlier comment than the one later selected (`check_a2_snapshots.py`); the
   same check runs on every new case before freezing.

   **Automatic check:** every line the reviewer quotes from the description (Markdown
   `>` quotes in the comment) must occur in the snapshot; a case where it does not is
   flagged and reviewed by hand before it enters the set.
7. **Freeze** the sampled set by URL and SHA-256 before any editing model runs on it,
   as for A2.

## What to report back before sampling

Counts per repository: pull requests in the window, comments pulled, keyword
survivors, LLM positives, spot-check precision/recall. The author decides the sample
size and whether to proceed from those numbers.

## Costs

GitHub API only, plus one classifier call per keyword survivor. Estimate the classifier
volume from the survivor count before running it.
