# Collecting real cases for the main study

The pilot ran on the existing 21 A2 cases. In parallel we build a larger candidate pool
so that the main study (`STUDY_PLAN.md`) samples real cases randomly instead of by
keyword. Nothing here involves running an editing model.

## Population

Pull requests whose title or description was criticized in review. "Representative"
means a random sample of that population, not of all pull requests.

## Procedure

1. **Repositories, by rule (2026-10-21; supersedes the hand-picked list below).** The
   list is generated, not chosen, and a large pool is pulled first; samples are drawn
   from the pool later. Script: `evals/study/select_repositories.py`; outputs under
   `$POLISH_EVAL_DATA/Processed/polish-open-source-prose/repo-selection/<version>/`.
   1. Eight fixed domains, in this order: systems and infrastructure, data systems, web
      back ends, ML frameworks, developer tools, scientific computing, languages and
      runtimes, front-end frameworks. Each domain has area topics (a field or
      technology) and kind topics (what the repository is: framework, library,
      compiler, database, ...). Every search query is one area topic and one kind
      topic, for all pairs, and excludes `self-hosted` and `awesome-list` plus a few
      per-domain topics (listed in the script); the GitHub search API rejects OR, so
      each pair is its own query. A domain's candidates are the union of its queries'
      results, cut to the 40 with the most stars. The exact query strings and the time
      of each query are recorded.
   2. Keep a repository only if it had at least 500 pull requests created between
      2025-10-01 and 2026-09-30, at most 25,000, and has a pull request template
      (`.github/PULL_REQUEST_TEMPLATE*` or `PULL_REQUEST_TEMPLATE*` in the root or
      `docs/`) and a contributing guide (`CONTRIBUTING*` in the root, `.github/`, or
      `docs/`).
   3. From each domain keep the 4 survivors with the most pull requests in the window:
      at most 32 repositories. A repository that qualifies in two domains counts in
      the first domain it appears in. A domain with fewer than 4 survivors is reported
      as it is, not refilled.
   4. The twelve repositories already pulled (list below) are reused where they appear
      on the generated list. **Sampling frame (author's decision, 2026-10-21; replaces
      the earlier rule that dropped the twelve not on the list):** v3's 28 repositories
      ∪ the twelve, 37 repositories, since airflow, django, and rust are on both. The
      twelve were chosen by hand before any comment was read. The eight domains are
      descriptive labels only; they play no part in sampling.
   4a. **Internal review imports (2026-10-21).** One rule for all 37: a repository is
      excluded if more than 25% of its pull requests created in the window were
      imported from an internal review system, so that their review did not happen on
      GitHub. A pull request counts as imported if its body contains one of these
      markers, fixed before any count was read: `Differential Revision:` (Phabricator),
      `Pull Request resolved:` and `fbshipit-source-id` (Meta's export), `Reviewed-on:`
      (Gerrit, with or without `Change-Id:`), `PiperOrigin-RevId`, `Copybara`, and
      `COPYBARA_INTEGRATE_REVIEW` (Google's Copybara). `Change-Id:` alone is recorded
      but not used, because projects that review on GitHub carry it too. The search API
      gives the number of pull requests in the window and the number with each marker in
      the body; marker counts are added when at most one is nonzero or no two overlap.
      When two overlap, or the added share reaches 5%, every body in the window is read
      through GraphQL and the markers are matched exactly, and that count decides (the
      search index ignores punctuation: `Reviewed-on:` matched 29 executorch bodies by
      search and none exactly). Script `evals/study/check_internal_review.py`; output
      `repo-selection/internal-review-check.json` (run 2026-10-20T23:52Z–2026-10-21T00:14Z).
      Result: pytorch/executorch is excluded (3,047 of 7,768, 39.2%, all `Differential
      Revision:`); every other repository is at or below 0.8%, so 36 remain. The check
      reads bodies only: a mirror that announces itself only through a bot comment, as
      golang/go's Gerrit bot does, would not be caught.
   5. Pull requests opened by the author of this study (ting-hong-shieh) are excluded,
      and so are repositories the author owns.
   6. After the author confirms the list, all pull requests and comments of every
      repository on it are pulled as raw data (one process, one token), in a recorded
      order with the time each repository took; the twelve pulled first are extended
      back to 2025-10-01. Sample sizes are decided afterwards (edit 80–120, keep 40).

      **Full pull (started 2026-10-21T00:24Z).** One process and one token, plan
      `pr-comments-2026/plans/full-2025-10-01_2026-09-30.json`: 36 jobs, about 111,500
      pull requests by search count. First the twelve repositories pulled earlier are
      extended back to 2025-10-01 (14,980 pull requests created 2025-10-01 to
      2025-12-31), in the order of the first pull; then the 24 new repositories for the
      whole window (96,563), in the order of `v3/selected.json`. The extension ran first
      because it is the smaller job, tests the changed collector on repositories with
      known counts, and completes the twelve repositories the classifier pass already
      uses. The start, end, and counts of each repository are in `collect.log`,
      `runs/full-2025-10-01_2026-09-30.jsonl`, and each `counts.json`.

      **How the extension merges.** Each extension is written to its own sub-run,
      `<owner>__<repo>/2025-10-01_2025-12-31/`, in the same layout; the 2026 files are not
      touched (their SHA-256 is in `MANIFEST-2026-01-01_2026-09-30.sha256`; the previous
      `WINDOW.json` and each `counts.json` are kept as `*.2026-01-01_2026-09-30.json`).
      `collect_pr_comments.py --stage merge` then appends each sub-run to the top-level
      files. The 2026 file stays a byte-identical prefix (its size and SHA-256 are
      recorded in `MERGE-2025-10-01_2025-12-31.json` and checked before the new file
      replaces it); rows of a pull request already present are skipped; `counts.json`
      gets the full window with both parts under "segments"; the sub-run is kept. Counts
      reported before the merge (the twelve-repository classifier pass, diff sizes) cover
      2026-01-01 to 2026-09-30 only.

      **Full pull result (2026-10-21, 00:24Z to 07:27Z, no job failed).** The twelve
      extensions (2025-10-01 to 2025-12-31): 14,985 pull requests, 73,062 issue comments,
      45,668 review comments. The 24 new repositories (full window): 96,569 pull requests,
      379,118 issue comments, 201,821 review comments. Pulled pull-request counts match
      the v3 search counts except cilium (+1), aiohttp (+1), and expo (+4), opened
      between the query and the pull. The process was interrupted twice (session end,
      WSL reboot) and resumed from its cursors; 44 rate-limit sleeps and 10 request
      retries, all recovered. Full table: `$POLISH_EVAL_DATA/Exports/polish-open-source-prose/study-runs/pull-report-2026-10-21.md`.

   **Rule versions.** v1 used single-topic queries and put applications in framework
   domains (flutter, angular and expo in web back ends; next.js in languages). v2
   dropped archived repositories and added `-topic:` exclusions, but its star-sorted
   single-topic queries still let in popular applications tagged with a technology
   they use (immich and coolify through `svelte`, gitea through `vue`, orca through
   `runtime`, volcano through `hpc`, backstage through `infrastructure`, streamlit
   through `machine-learning`). v3 adds the area-and-kind pairing of step 1.1; its
   rule was written to `v3/RULE.md` (2026-10-20T20:15Z) before any v3 query and it
   was run once. The outputs of all three are kept (`run1/`, `v2/`, `v3/`). v3
   selected 28 repositories with 133,201 pull requests in the window: ML frameworks
   has 3 and scientific computing 1, because few repositories in those fields carry
   a kind topic, and large projects that tag no kind topic (kubernetes, node, vscode,
   transformers, scikit-learn, scipy) are no longer on the list. Of the twelve
   already pulled, airflow, rust and django remain. The v3 list awaits the author's
   confirmation.

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
   pull request in batched GraphQL queries sized by those counts. Review summaries
   (the body a reviewer writes with approve/request-changes) are taken from the first
   20 reviews of a pull request; 1,485 of 111,554 pull requests in the full pull (1.3%)
   have more than 20 and lose the later summaries. Review thread comments and issue
   comments are paginated with cursors and complete. A first version used
   the repository-wide REST comment listings and was dropped: their `since` parameter
   filters by update time, so pages fill with old comments that bots re-edited and the
   cursor stalls (apache/airflow stopped at 2026-03-12). The edit history is stored as
   the edit count per pull request; the edits themselves are fetched later only for
   sampled cases.
4. **Classify.** Two passes:
   - a pre-filter (2026-10-21), applied before anything else reads the comments: drop
     comments whose author is a bot (`[bot]` accounts and the known project bots listed
     in `classify_comments.py`), comments written by the pull request's own author
     (login from `pulls.jsonl`), and comments with no author login (deleted accounts);
     the reviewer's critique is what we want, not the author's reply or self-report.
     On a backport that a bot opened (miss-islington, github-actions), the authors of
     the pull requests its title references (`#N`, `GH-N`) count as its authors too
     (added 2026-10-21: the 12-repository pass let 4 such comments through; a
     referenced pull request outside the window is missed). Comments by the study's
     author, and comments on the study author's pull requests, are dropped here as well.
     Two more exclusions (author's decision, 2026-10-21):
     - **AI-written reviews.** A comment carrying an HTML-comment marker written by an AI
       review tool is dropped, even when it is posted under a person's account. The
       marker list in `classify_comments.py` (`AI_REVIEW`) was fixed from a survey of
       every HTML-comment marker in the twelve-repository pull: apache/spark's review
       tooling (`ai-code-review`, `ai-auto-review-authorized`, `spark_dev_review_*`,
       `spark-dev-review-delivery`) and Codex review summaries and withdrawals. The
       survey is rerun on the full pull before classification; a new marker is added with
       its date.
     - **AI-drafted comments marked in plain text** (added 2026-10-21 after the spot check
       drew an apache/airflow review ending "This review was drafted by an AI-assisted tool
       and confirmed by an Apache Airflow maintainer"). A phrase scan of all 36 repositories
       ("drafted by", "AI-assisted", "generated review", "automated review", "generated
       by/with <model>", "Drafted-by:", …) found the templates; `ai_disclosed()` in
       `classify_comments.py` drops a comment that says of itself that it was drafted or
       generated by an AI tool: "This review/comment/assessment was drafted/generated by an
       AI …", a `Drafted-by:`/`Generated-by:`/`Assisted-by:` trailer, "🤖 Generated with
       Claude Code", "🤖 This is an automated review", "AI-generated comment (", the GitHub
       MCP footer, "AI-/LLM-assisted review" said of the comment itself, and a few more.
       Fenced code is ignored, and trailers inside a quote are not matched: a reviewer quoting
       the pull request's own disclosure, or writing about AI-generated pull requests, is a
       critique the study keeps. 3,696 comments dropped (apache/airflow 3,307); 371 keyword
       survivors removed, 143 of them positives.
     - **Templated comments.** A comment is dropped when the same account posted the same
       text at least five times in the pulled data (same after lower-casing, collapsing
       whitespace, and writing every @mention as "@" and every run of digits as "0").
     Twelve-repository pool (2026-10-21): the AI-review rule drops 1,975 comments and the
     template rule 8,526; of the 10,200 keyword survivors they remove 700 and 236, and of
     the 3,523 classifier positives 350 (all apache/spark) and 42 (kubernetes 26, airflow
     16), leaving 3,131 positives. Counts per repository are in
     `classifier-full-12/prefilter-r3/stage-counts.json`.
     Full-frame survey (2026-10-21, 36 repositories, after the merge; `classifier-full-36/`
     `marker-survey.json`, `author-survey.json`): 15,304 distinct HTML-comment markers. Added
     to `AI_REVIEW`: apache/doris local pipeline reviews (`doris-repo-review`, "model:
     gpt-6-astra") and agent re-check responses (`autopilot-response`); kestra's auto review
     posted by a member (`kestra-auto-review`); expo's docs/style reviewer (`wm-review`,
     `docs-review`) and its AI code reviewer when a person re-posts it
     (`expo-ai-code-reviewer`); prefect's dependency review (`claude-dep-review`); mirrord's
     auto-approve verdicts (`jev-auto-approve`); StarRocks' agent validation and e2e reports
     (`ship-pr-validation-report`, `ship-pr-e2e-report`). Seen and not added: a GitHub MCP
     attribution footer on a person's own comment, agent handoff notes by the pull request's
     author, a CI-generated OpenAPI report, Graphite stack lists, Linear-synced replies. The
     same survey and the keyword survivors showed 40 automation logins without the `[bot]`
     suffix (CI, coverage, merge queue, CLA, preview, size, security and AI reviewer apps,
     and accounts that only post `@codex review`/`@cursor review`); they are added to the bot
     list with the date. AI-written reviews under a person's account and without a marker
     (one stdlib "Issue Reference Review" check, a few "Automated Code Review" posts, agent
     approvals on kestra) cannot be dropped by rule and go to the classifier, whose prompt
     counts bot output as no.
     Full-frame pre-filter (2026-10-21, 1,273,626 comment items): bots 546,595, the pull
     request's author 230,369, under 20 characters 141,454, templated 24,485, AI-review
     markers 2,805 (apache/spark 1,977, expo 608, doris 103), no login 1,106; 326,812 items
     remain and 15,775 match the keyword pass (`classifier-full-36/stage-counts.json`).
     Full-frame LLM pass (2026-10-21): Haiku 5.5, same prompt; 9,264 answers reused from the
     twelve-repository pass, 6,511 new calls (USD 7.23; frame total USD 14.03), no failures.
     5,215 positives (33.1% of survivors) in 4,268 pull requests. Of the twelve-repository
     answers, 940 (393 positives) fall away under the extended pre-filter. Diff sizes: 10.4%
     of pull requests with a positive and 5.4% of landed pull requests exceed 1,500 lines.
     After the plain-text AI-disclosure rule (revision 3): 15,404 keyword survivors, 5,072
     positives (32.9%) in 4,151 pull requests; 10.4% of those pull requests exceed 1,500
     lines. The author's spot check uses 50 positives and 50 negatives drawn from revision 3
     (seed 20261021, stratified by repository; `--sheet-format lines`: the classifier's quoted
     sentence, the first 400 characters, the link, the full comment folded). The classifier
     quotes a sentence only on a yes, so that layout shows the label; `--sheet-format
     lines-keyword` gives the same items with the keyword-matched sentence instead. Per-repository table:
     `$POLISH_EVAL_DATA/Exports/polish-open-source-prose/study-runs/classifier-report-36-2026-10-21.md`.
     Counts are reported per repository at each stage (all comments, after the
     pre-filter, after keywords, positives);
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
     precision and recall of the classifier. These numbers go in the paper. Order
     (2026-10-21): the full pass runs first on the twelve repositories already pulled;
     a Claude session checks 30 random positives from it for bots or pull request
     authors that slipped through the pre-filter, and the pre-filter is fixed if any
     did; the author's spot check is drawn after the full pass over the whole confirmed
     list (`classify_comments.py --spot-check 50 --seed S`, seed recorded).
5. **Sample.** From the positives, a random sample (seed fixed in advance), stratified
   by repository so no single project dominates: 80–120 edit candidates, of which about
   80 are kept after the author's flags, plus 40 keep cases, drawn from the merged pull
   requests of the same repositories and window that have no comment classified as a
   critique. **Allocation (2026-10-21):** each repository's share is proportional to its
   eligible candidates, capped at 10% of the set (at most 8 of 80 edit cases and 4 of 40
   keep cases per repository); what the cap removes is redistributed in proportion among
   the repositories under the cap; within a repository, pull requests are drawn in
   seeded random order, at most one case per pull request. Exclusions, applied to the
   pool before the draw and reported with counts per repository:
   - **Study author.** Pull requests opened by the author of this study
     (ting-hong-shieh), and comments the author wrote, are excluded.
   - **Bots and the pull request's author.** Only comments that passed the pre-filter
     of step 4 can make a pull request an edit case; a critique by a bot or by the
     pull request's own author does not count.
   - **Diff size (2026-10-21).** A pull request whose diff exceeds 1,500 lines (added
     plus removed, counted from the patch) is excluded from both sets: for edit
     candidates, the diff at the selected comment's timestamp; for keep candidates,
     the merged diff. No diff is truncated for the editor. The pilot showed that a few
     very large diffs dominate cost and judge load (two A2 diffs of about 4,480 patch
     lines); excluding them by a rule keeps every editor and judge looking at the whole
     diff. The share excluded is reported for the pool (using the pull request's final
     size, before the draw) and for the drawn cases (using the diff at the timestamp).
     Twelve-repository pool, 2026-10-21 (`pr_sizes.py`, final sizes): 223 of 2,699 pull
     requests with a classifier positive (8.3%) and 1,647 of 41,080 landed pull
     requests (4.0%) exceed the limit.
     When a drawn edit case turns out to exceed the limit at its timestamp, it is
     replaced by the next case in the seeded order of the same repository.
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

Counts per repository: pull requests in the window, comments pulled, comments after
the pre-filter, keyword survivors, LLM positives, pull requests excluded by the diff-size
rule, spot-check precision/recall. The author decides the sample size and whether to
proceed from those numbers.

## Costs

GitHub API only, plus one classifier call per keyword survivor. Estimate the classifier
volume from the survivor count before running it.
