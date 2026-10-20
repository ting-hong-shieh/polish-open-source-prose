# Collecting more real cases (for a later round, not round 4)

Round 4 runs on the existing 21 A2 cases. In parallel, and without touching round 4, we
build a larger candidate pool so that a later round can sample real cases randomly
instead of by keyword. Nothing here involves running an editing model.

## Population

Pull requests whose title or description was criticized in review. "Representative"
means a random sample of that population, not of all pull requests.

## Procedure

1. **Repositories, by rule (2026-10-21; supersedes the hand-picked list below).** The
   list is generated, not chosen, and a large pool is pulled first; samples are drawn
   from the pool later.
   1. Fix 6–8 domains (for example: systems and infrastructure, data systems, web
      back ends, ML frameworks, developer tools, scientific computing, languages and
      runtimes, front-end frameworks). For each domain, take the 40 repositories with
      the most stars from the GitHub search API, and record the exact query string and
      the date of the query (`evals/study/select_repositories.py`).
   2. Keep a repository only if it had at least 500 pull requests created between
      2025-10-01 and 2026-09-30, at most 25,000, and has a pull request template
      (`.github/PULL_REQUEST_TEMPLATE*` or `PULL_REQUEST_TEMPLATE*` in the root or
      `docs/`) and a contributing guide (`CONTRIBUTING*` in the root, `.github/`, or
      `docs/`).
   3. From each domain keep the 4 survivors with the most pull requests in the window:
      25–30 repositories in all. A repository that qualifies in two domains counts in
      the first domain it appears in.
   4. The twelve repositories already pulled (list below) are reused where they appear
      on the generated list; those that do not appear are kept as raw data but are not
      part of the pool.
   5. Pull requests opened by the author of this study (ting-hong-shieh) are excluded.
   6. After the author confirms the list, all pull requests and comments of every
      repository on it are pulled as raw data (one process, one token), in a recorded
      order with the time each repository took. Sample sizes are decided afterwards
      (edit 80–120, keep 40).

   **Hand-picked list (2026-10-20), fixed before reading any comment; kept for the
   record and as the first part of the raw data:** apache/airflow,
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

   **Fixed window:** 2025-10-01 to 2026-09-30, by pull request creation date (the
   first twelve repositories were pulled for 2026-01-01 to 2026-09-30 and are extended
   back to 2025-10-01 in the full pull).
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
   - a pre-filter (2026-10-21): drop comments whose author is a bot (`[bot]` accounts
     and the known project bots listed in `classify_comments.py`) and comments written
     by the pull request's own author (login from `pulls.jsonl`); the reviewer's
     critique is what we want, not the author's reply or self-report;
   - a cheap keyword pass (description, title, "does not match", "AI-generated",
     "evidence", "claim", "misleading", "please update the description", …) to cut
     the volume. Terms that match automated footers or bot names rather than
     critiques (`claude`, `copilot`, …) are left out: in the trial 40% of survivors
     matched only those and yielded no positives;
   - an LLM pass on the survivors with one question: does this comment criticize the
     pull request's title or description text (not only the code)? Output yes/no and
     the quoted sentence. One model, fixed prompt, committed before running: Claude
     Haiku 5.5 through Claude Code (chosen 2026-10-21 after a 100-comment trial against
     GPT-6 Astra, κ = 0.85 between the two; about USD 0.0007 per call).
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
