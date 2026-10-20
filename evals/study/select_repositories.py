#!/usr/bin/env python3
"""Generate the repository list for the larger case pool by rule (CASE_COLLECTION.md, step 1).
No comments, no pull request bodies, no model: search counts and directory listings only.

Rule:
1. Eight fixed domains. For each, the 40 non-archived repositories with the most stars from
   the GitHub search API. The API rejects OR between qualifiers, so each domain is the union
   of several `topic:` queries (recorded verbatim, with `-topic:` exclusions; from v3 each
   query is an area topic AND a kind topic), cut to the 40 with the most stars.
2. Keep a repository only if it had 500-25,000 pull requests created in the window
   (search/issues total_count), has a pull request template (`PULL_REQUEST_TEMPLATE*`, file
   or directory, in `.github/`, the root, or `docs/`) and a contributing guide
   (`CONTRIBUTING*` in the root, `.github/`, or `docs/`), matched without regard to case
   through the contents API directory listings, and is not owned by the study's author.
3. From each domain, the 4 survivors with the most pull requests in the window. A repository
   that appears in two domains belongs to the first (domain order below).
4. Mark the twelve repositories already pulled.

Rule versions (the queries of each are kept below as data):
- v1 (2026-10-20): single-topic queries; outputs in run1/.
- v2 (2026-10-20): archived repositories excluded, six domains tightened with `-topic:`
  exclusions; outputs in v2/ (and, identical, at the top of the output directory).
- v3 (2026-10-21): co-tag rule. Every query is `topic:<area> topic:<kind>`: one topic for
  the domain's field or technology and one that names what the repository is (framework,
  library, compiler, database, ...), so a repository tagged only with a technology it uses
  (svelte, vue, runtime, cli, database, hpc, machine-learning) no longer qualifies. Every
  query also excludes `self-hosted` and `awesome-list`, and each domain's v2 exclusions
  apply to all of its queries. Outputs in v3/; the rule was written to v3/RULE.md before
  the run, and the run refuses to start if the rule no longer matches that file.

Every API response is cached as JSON under cache/ (shared by all versions, write-once), so
a rerun makes no calls and a later version reuses earlier pull request counts and
directory listings. Search calls are spaced 2.5 s apart (limit 30/min). Directory listings
are fetched only for repositories that pass the pull request count.

Writes under $POLISH_EVAL_DATA/Processed/polish-open-source-prose/repo-selection/<version>/:
RULE.md (with --write-rule, before the run), candidates.json, selected.json, REPORT.md.
A version's outputs are never overwritten.

Usage: POLISH_EVAL_DATA=/mnt/d/Data python3 -I evals/study/select_repositories.py --write-rule
       POLISH_EVAL_DATA=/mnt/d/Data python3 -I evals/study/select_repositories.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DATA = Path(os.environ.get("POLISH_EVAL_DATA", "/mnt/d/Data"))
OUT = DATA / "Processed/polish-open-source-prose/repo-selection"
CACHE = OUT / "cache"

WINDOW_START, WINDOW_END = "2025-10-01", "2026-09-30"
MIN_PRS, MAX_PRS = 500, 25_000
PER_DOMAIN_CANDIDATES, PER_DOMAIN_KEEP = 40, 4
SEARCH_GAP_S = 2.5

# Order matters: a repository that appears in two domains belongs to the first.
# Second version (2026-10-21): archived repositories excluded; six domains tightened after the
# first run mislabeled flutter/angular/expo (web-backend), next.js (languages), bun (frontend),
# OpenTTD (scientific), worldmonitor (systems), paperclip/deer-flow (ml). The first run's
# outputs are kept under run1/ in the output directory. Kept for the record; not run again.
A = " archived:false"
DOMAINS_V2: list[tuple[str, list[str]]] = [
    ("systems-and-infrastructure",
     ["topic:kubernetes" + A, "topic:infrastructure" + A, "topic:containers" + A,
      "topic:distributed-systems" + A, "topic:cloud-native" + A]),
    ("data-systems",
     ["topic:database" + A, "topic:sql" + A, "topic:data-engineering" + A, "topic:big-data" + A, "topic:olap" + A]),
    ("web-backend",
     ["topic:backend -topic:frontend -topic:mobile" + A,
      "topic:web-framework -topic:frontend -topic:mobile -topic:pwa" + A,
      "topic:http-server" + A, "topic:web-server" + A, "topic:orm" + A]),
    ("ml-frameworks",
     ["topic:machine-learning -topic:ai-agents -topic:agent -topic:agents -topic:llm-app" + A,
      "topic:deep-learning -topic:ai-agents -topic:agent -topic:agents -topic:llm-app" + A,
      "topic:ml-framework" + A, "topic:tensor" + A, "topic:neural-network" + A]),
    ("developer-tools",
     ["topic:developer-tools" + A, "topic:cli" + A, "topic:editor" + A, "topic:build-tool" + A, "topic:linter" + A]),
    ("scientific-computing",
     ["topic:scientific-computing" + A, "topic:numerical-methods" + A, "topic:linear-algebra" + A,
      "topic:hpc" + A, "topic:simulation -topic:game -topic:games -topic:game-engine" + A]),
    ("languages-and-runtimes",
     ["topic:programming-language" + A, "topic:compiler -topic:react" + A, "topic:interpreter" + A,
      "topic:runtime" + A, "topic:jit" + A]),
    ("frontend-frameworks",
     ["topic:frontend" + A, "topic:ui-framework" + A, "topic:react-framework" + A, "topic:vue" + A,
      "topic:svelte" + A]),
]

# Third version (2026-10-21), fixed from the v2 diagnosis before any v3 query ran. In v2 a
# star-sorted single-topic query let in popular applications that carry a topic for a
# technology they use: immich and coolify (svelte) and gitea (vue) in front-end frameworks,
# orca (runtime) in languages, volcano (hpc) and burn (scientific-computing) in scientific
# computing, backstage (infrastructure) in systems, streamlit (machine-learning) in ML
# frameworks, n8n and gemini-cli (cli) in developer tools, metabase (database) and superset
# (data-engineering) in data systems. Rule: every query pairs one area topic with one kind
# topic (all area x kind pairs); areas are v2's topics that name a field or technology,
# kinds are v2's topics that name a kind of software plus kind nouns added per domain.
# Every query excludes self-hosted (deployable applications) and awesome-list (link lists);
# each domain's v2 exclusions now apply to all of its queries.
RULE_V3: dict = {
    "version": "v3",
    "global_exclude": ["self-hosted", "awesome-list"],
    "domains": [
        {"domain": "systems-and-infrastructure",
         "areas": ["kubernetes", "cloud-native", "distributed-systems", "containers", "infrastructure"],
         "kinds": ["orchestration", "container-runtime", "scheduler", "service-mesh", "networking", "storage",
                   "monitoring"],
         "exclude": []},
        {"domain": "data-systems",
         "areas": ["sql", "big-data", "data-engineering", "olap"],
         "kinds": ["database", "distributed-database", "query-engine", "dataframe", "stream-processing", "etl"],
         "exclude": []},
        {"domain": "web-backend",
         "areas": ["backend", "web", "http"],
         "kinds": ["web-framework", "framework", "http-server", "web-server", "orm"],
         "exclude": ["frontend", "mobile", "pwa"]},
        {"domain": "ml-frameworks",
         "areas": ["machine-learning", "deep-learning", "neural-network"],
         "kinds": ["ml-framework", "deep-learning-framework", "framework", "library", "toolkit", "tensor"],
         "exclude": ["ai-agents", "agent", "agents", "llm-app"]},
        {"domain": "developer-tools",
         "areas": ["developer-tools", "cli"],
         "kinds": ["editor", "ide", "build-tool", "linter", "formatter", "debugger", "package-manager", "bundler"],
         "exclude": []},
        {"domain": "scientific-computing",
         "areas": ["scientific-computing", "numerical-methods", "linear-algebra", "hpc", "simulation"],
         "kinds": ["library", "framework", "toolkit", "solver"],
         "exclude": ["game", "games", "game-engine"]},
        {"domain": "languages-and-runtimes",
         "areas": ["programming-language", "language"],
         "kinds": ["compiler", "interpreter", "runtime", "jit", "virtual-machine"],
         "exclude": ["react"]},
        {"domain": "frontend-frameworks",
         "areas": ["frontend", "vue", "svelte"],
         "kinds": ["framework", "library", "ui-framework", "react-framework"],
         "exclude": []},
    ],
}

RULE_V3_TEXT = """\
Every search query is `topic:<area> topic:<kind>`: one topic that names the domain's field
or technology (area) and one that names what the repository is (kind: a framework, library,
compiler, database, ...). A domain's queries are all its area x kind pairs; its candidates
are their union, cut to the 40 with the most stars. A repository tagged only with a
technology it uses (svelte, vue, runtime, cli, database, hpc, machine-learning) no longer
qualifies. Every query also excludes `topic:self-hosted` (applications one deploys) and
`topic:awesome-list` (link lists), and each domain's v2 exclusions (web-backend: frontend,
mobile, pwa; ml-frameworks: ai-agents, agent, agents, llm-app; scientific-computing: game,
games, game-engine; languages-and-runtimes: react) apply to all of that domain's queries.
Areas are v2's topics that name a field or technology; kinds are v2's topics that name a
kind of software (database, web-framework, http-server, web-server, orm, ml-framework,
tensor, editor, build-tool, linter, compiler, interpreter, runtime, jit, ui-framework,
react-framework) plus kind nouns added per domain; v2's `programming-language` becomes an
area, with `language` added beside it, and web-backend gains the areas `web` and `http`
because `backend` was its only area topic. Unchanged from v2: pull requests created
2025-10-01..2026-09-30, 500-25,000 of them; a pull request template and a contributing
guide; 40 candidates per domain by stars; 4 per domain by pull requests; a repository
counts in the first domain it appears in (domain order as listed); repositories owned by
the study's author (ting-hong-shieh) are excluded."""


def build_queries(rule: dict) -> list[tuple[str, list[str]]]:
    out = []
    for d in rule["domains"]:
        excl = "".join(f" -topic:{t}" for t in d["exclude"] + rule["global_exclude"])
        out.append((d["domain"], [f"topic:{a} topic:{k}{excl}{A}" for a in d["areas"] for k in d["kinds"]]))
    return out


RULE_VERSION = RULE_V3["version"]
DOMAINS: list[tuple[str, list[str]]] = build_queries(RULE_V3)
RULE_SHA256 = hashlib.sha256(json.dumps({"rule": RULE_V3, "text": RULE_V3_TEXT, "queries": DOMAINS},
                                        sort_keys=True).encode()).hexdigest()
RUN = OUT / RULE_VERSION
AUTHOR_OWNERS = ["ting-hong-shieh"]  # the study author's own repositories are excluded

ALREADY_PULLED = ["apache/airflow", "apache/datafusion", "apache/arrow", "python/cpython",
                  "kubernetes/kubernetes", "rust-lang/rust", "pandas-dev/pandas", "numpy/numpy",
                  "nodejs/node", "prometheus/prometheus", "apache/spark", "django/django"]

TEMPLATE_DIRS = [".github", "", "docs"]      # where PULL_REQUEST_TEMPLATE* may live
CONTRIBUTING_DIRS = ["", ".github", "docs"]  # where CONTRIBUTING* may live

_last_search = 0.0


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class NotFound(Exception):
    pass


def gh(*args: str, search: bool = False) -> str:
    """Run gh api and return stdout (JSON). 404 raises NotFound; rate limits sleep until reset;
    transient errors retry with backoff."""
    global _last_search
    attempt = 0
    while True:
        if search:
            wait = SEARCH_GAP_S - (time.monotonic() - _last_search)
            if wait > 0:
                time.sleep(wait)
        p = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
        if search:
            _last_search = time.monotonic()
        if p.returncode == 0:
            try:
                json.loads(p.stdout)
                return p.stdout
            except json.JSONDecodeError as exc:
                p.stderr = f"truncated json: {exc}"
        err = p.stderr.lower()
        if "http 404" in err or "http 422" in err:  # missing path, or a repository the search cannot see
            raise NotFound(p.stderr.strip()[:200])
        if "rate limit" in err or "ratelimit" in err or "http 429" in err:
            try:
                lim = json.loads(subprocess.run(["gh", "api", "rate_limit"], capture_output=True, text=True).stdout)
                res = lim["resources"]["search" if search else "core"]
                wait = max(10, res["reset"] - int(time.time()) + 5)
            except Exception:
                wait = 90
            print(f"  rate limit ({'search' if search else 'core'}): sleeping {wait}s", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        attempt += 1
        if attempt <= 6 and any(k in err for k in ("secondary", "502", "503", "504", "timeout", "unexpected end",
                                                     "connection", "eof", "abuse", "something went wrong",
                                                     "truncated json")):
            wait = 60 * attempt
            print(f"  retry in {wait}s: {p.stderr.strip()[:120]}", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(p.stderr.strip()[:500])


def cached(path: Path, fetch, *, search: bool = False) -> dict:
    """Return the cached JSON at `path`, or call fetch() (returning a JSON string, or raising
    NotFound), wrap it with the fetch time, and store it."""
    if path.exists():
        return json.loads(path.read_text())
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        body = json.loads(fetch())
        rec = {"fetched_at": now_iso(), "status": 200, "body": body}
    except NotFound:
        rec = {"fetched_at": now_iso(), "status": 404, "body": None}
    path.write_text(json.dumps(rec, indent=1))
    return rec


def slug(repo: str) -> str:
    return repo.replace("/", "__")


# ----------------------------------------------------------------------------- step 1

def search_repositories(query: str) -> dict:
    key = hashlib.sha1(query.encode()).hexdigest()[:12]
    path = CACHE / "search_repositories" / f"{key}.json"

    def fetch() -> str:  # a rejected query must stop the run, not be cached as an empty result
        try:
            return gh("-X", "GET", "search/repositories", "-f", f"q={query}", "-f", "sort=stars",
                      "-f", "order=desc", "-f", f"per_page={PER_DOMAIN_CANDIDATES}", search=True)
        except NotFound as exc:
            raise RuntimeError(f"search rejected: {query}: {exc}") from exc

    rec = cached(path, fetch, search=True)
    rec["query"] = query
    return rec


def repo_record(item: dict) -> dict:
    return {
        "repo": item["full_name"],
        "stars": item["stargazers_count"],
        "archived": item.get("archived", False),
        "fork": item.get("fork", False),
        "mirror_url": item.get("mirror_url"),
        "default_branch": item.get("default_branch"),
        "pushed_at": item.get("pushed_at"),
        "language": item.get("language"),
        "topics": item.get("topics", []),
        "description": (item.get("description") or "")[:200],
    }


def domain_candidates() -> tuple[list[dict], list[dict]]:
    """Returns (queries, candidates). candidates: one record per (domain, repo), with the
    domain's rank by stars; the same repo may appear under several domains."""
    queries, candidates = [], []
    for domain, qs in DOMAINS:
        pool: dict[str, dict] = {}
        for q in qs:
            rec = search_repositories(q)
            items = rec["body"]["items"] if rec["body"] else []
            queries.append({"domain": domain, "query": q, "fetched_at": rec["fetched_at"],
                            "total_count": rec["body"]["total_count"] if rec["body"] else None,
                            "returned": len(items)})
            for it in items:
                r = repo_record(it)
                r.setdefault("matched_queries", [])
                if it["full_name"] in pool:
                    pool[it["full_name"]]["matched_queries"].append(q)
                else:
                    r["matched_queries"] = [q]
                    pool[it["full_name"]] = r
        top = sorted(pool.values(), key=lambda r: (-r["stars"], r["repo"]))[:PER_DOMAIN_CANDIDATES]
        for rank, r in enumerate(top, 1):
            candidates.append({"domain": domain, "domain_rank_by_stars": rank, **r})
        print(f"{domain}: {len(pool)} distinct from {len(qs)} queries, kept {len(top)}", file=sys.stderr, flush=True)
    return queries, candidates


# ----------------------------------------------------------------------------- step 2

def pr_count(repo: str) -> dict:
    path = CACHE / "pr_count" / f"{slug(repo)}.json"
    q = f"repo:{repo} is:pr created:{WINDOW_START}..{WINDOW_END}"
    rec = cached(path, lambda: gh("-X", "GET", "search/issues", "-f", f"q={q}", "-f", "per_page=1", search=True),
                 search=True)
    return {"pr_count": rec["body"]["total_count"] if rec["body"] else None,
            "pr_count_fetched_at": rec["fetched_at"], "pr_count_query": q}


def listing(repo: str, directory: str) -> list[dict] | None:
    """Directory listing from the contents API (default branch), or None if it does not exist."""
    name = directory or "ROOT"
    path = CACHE / "contents" / slug(repo) / f"{name.replace('/', '__')}.json"
    endpoint = f"repos/{repo}/contents/{directory}" if directory else f"repos/{repo}/contents"
    rec = cached(path, lambda: gh("-X", "GET", endpoint, "-f", "per_page=1000"))
    body = rec["body"]
    if body is None or not isinstance(body, list):
        return None
    return [{"name": e["name"], "type": e["type"], "path": e["path"]} for e in body]


def find_files(repo: str, dirs: list[str], prefix: str) -> list[dict]:
    found = []
    for d in dirs:
        entries = listing(repo, d) or []
        for e in entries:
            if e["name"].upper().startswith(prefix):
                hit = {"path": e["path"], "type": e["type"]}
                if e["type"] == "dir":
                    inner = listing(repo, e["path"]) or []
                    hit["files"] = [x["path"] for x in inner]
                found.append(hit)
    return found


def check_repo(r: dict) -> dict:
    """Fill in pr_count, template, contributing, pass flags, and reasons for one repository."""
    r.update(pr_count(r["repo"]))
    reasons = []
    n = r["pr_count"]
    r["pass_pr_count"] = n is not None and MIN_PRS <= n <= MAX_PRS
    if n is None:
        reasons.append("pr count unavailable")
    elif n < MIN_PRS:
        reasons.append(f"too few pull requests in window ({n} < {MIN_PRS})")
    elif n > MAX_PRS:
        reasons.append(f"too many pull requests in window ({n} > {MAX_PRS})")
    if r["pass_pr_count"]:
        r["pr_templates"] = find_files(r["repo"], TEMPLATE_DIRS, "PULL_REQUEST_TEMPLATE")
        r["contributing"] = find_files(r["repo"], CONTRIBUTING_DIRS, "CONTRIBUTING")
        r["pass_template"] = bool(r["pr_templates"])
        r["pass_contributing"] = bool(r["contributing"])
        r["template_is_directory_only"] = bool(r["pr_templates"]) and all(t["type"] == "dir" for t in r["pr_templates"])
        if not r["pass_template"]:
            reasons.append("no pull request template")
        if not r["pass_contributing"]:
            reasons.append("no contributing guide")
    else:
        r["pr_templates"], r["contributing"] = None, None
        r["pass_template"] = r["pass_contributing"] = None
        r["template_is_directory_only"] = None
        reasons.append("files not checked")
    r["authors_own"] = r["repo"].split("/")[0].lower() in [o.lower() for o in AUTHOR_OWNERS]
    if r["authors_own"]:
        reasons.append("the study author's own repository")
    r["survivor"] = bool(r["pass_pr_count"] and r["pass_template"] and r["pass_contributing"]
                         and not r["authors_own"])
    r["reasons"] = reasons
    r["already_pulled"] = r["repo"] in ALREADY_PULLED
    return r


# ----------------------------------------------------------------------------- step 3

def select(candidates: list[dict]) -> list[dict]:
    """Assign each repo to the first domain it appears in, then keep the top 4 survivors per
    domain by pull request count."""
    first_domain: dict[str, str] = {}
    other_domains: dict[str, list[str]] = {}
    for c in candidates:  # candidates are in domain order
        if c["repo"] not in first_domain:
            first_domain[c["repo"]] = c["domain"]
        elif c["domain"] != first_domain[c["repo"]]:
            other_domains.setdefault(c["repo"], []).append(c["domain"])
    for c in candidates:
        c["assigned_domain"] = first_domain[c["repo"]]
        c["also_in_domains"] = other_domains.get(c["repo"], [])
        c["selected"] = False
        c["selection_note"] = ""
    selected = []
    for domain, _ in DOMAINS:
        own = [c for c in candidates if c["domain"] == domain and c["assigned_domain"] == domain]
        foreign = [c for c in candidates if c["domain"] == domain and c["assigned_domain"] != domain]
        for c in foreign:
            c["selection_note"] = f"counted in {c['assigned_domain']}"
        surv = sorted([c for c in own if c["survivor"]], key=lambda c: (-c["pr_count"], c["repo"]))
        for i, c in enumerate(surv):
            if i < PER_DOMAIN_KEEP:
                c["selected"] = True
                c["selection_note"] = f"top {PER_DOMAIN_KEEP} by pull requests"
                selected.append(c)
            else:
                c["selection_note"] = f"survivor, rank {i + 1} by pull requests"
    return selected


# ----------------------------------------------------------------------------- report

def md_table(rows: list[dict]) -> str:
    head = "| # | repo | stars | PRs in window | PR template | contributing | selected | reason |"
    sep = "|---|---|---:|---:|---|---|---|---|"
    lines = [head, sep]
    for c in rows:
        tpl = "not checked" if c["pr_templates"] is None else (
            "; ".join(t["path"] + ("/ (dir, %d files)" % len(t["files"]) if t["type"] == "dir" else "")
                      for t in c["pr_templates"]) or "none")
        con = "not checked" if c["contributing"] is None else (
            "; ".join(t["path"] for t in c["contributing"]) or "none")
        flags = []
        if c["archived"]:
            flags.append("archived")
        if c["mirror_url"]:
            flags.append("mirror")
        if c["fork"]:
            flags.append("fork")
        if c["already_pulled"]:
            flags.append("already pulled")
        name = f"{c['repo']}" + (f" ({', '.join(flags)})" if flags else "")
        if c["selected"]:
            reason = c["selection_note"]
        elif c["selection_note"]:
            reason = c["selection_note"]
        else:
            reason = "; ".join(x for x in c["reasons"] if x != "files not checked")
        prs = "" if c["pr_count"] is None else f"{c['pr_count']:,}"
        lines.append(f"| {c['domain_rank_by_stars']} | {name} | {c['stars']:,} | {prs} | {tpl} | {con} | "
                     f"{'yes' if c['selected'] else 'no'} | {reason} |")
    return "\n".join(lines)


def pairs_of(c: dict) -> str:
    """The area+kind pairs of a candidate's matched queries, e.g. 'frontend+library'."""
    return ", ".join("+".join(t.split(":", 1)[1] for t in q.split()[:2]) for q in c["matched_queries"])


def eligible_pairs(topics: list[str]) -> list[tuple[str, str]]:
    """(domain, 'area+kind') pairs a repository with these topics could match under the rule,
    ignoring the cut to the top 40 by stars."""
    out = []
    excl_all = set(RULE_V3["global_exclude"])
    for d in RULE_V3["domains"]:
        if set(topics) & (excl_all | set(d["exclude"])):
            continue
        out += [(d["domain"], f"{a}+{k}") for a in d["areas"] for k in d["kinds"] if a in topics and k in topics]
    return out


def changes_from(prev_path: Path, candidates: list[dict], selected: list[dict]) -> list[str]:
    if not prev_path.exists():
        return [f"No earlier list at {prev_path}.", ""]
    prev = json.loads(prev_path.read_text())
    prev_cands = {}
    prev_cand_path = prev_path.parent / "candidates.json"
    if prev_cand_path.exists():
        for c in json.loads(prev_cand_path.read_text())["candidates"]:
            prev_cands.setdefault(c["repo"], c)
    prev_sel = {c["repo"]: c for c in prev["selected"]}
    now_sel = {c["repo"]: c for c in selected}
    out = [f"Kept ({len(set(prev_sel) & set(now_sel))}): "
           + ", ".join(f"{r}" for r in now_sel if r in prev_sel) + ".", "",
           f"Dropped ({len(set(prev_sel) - set(now_sel))}):", ""]
    for r, pc in prev_sel.items():
        if r in now_sel:
            continue
        cs = [c for c in candidates if c["repo"] == r]
        if cs:
            c = cs[0]
            why = c["selection_note"] or "; ".join(x for x in c["reasons"] if x != "files not checked")
            out.append(f"- {r} (v2: {pc['domain']}): candidate in {c['domain']} via {pairs_of(c)}; {why}.")
        else:
            topics = prev_cands.get(r, {}).get("topics", [])
            ep = eligible_pairs(topics)
            if ep:
                out.append(f"- {r} (v2: {pc['domain']}): its topics match {', '.join(f'{d} {p}' for d, p in ep)}, "
                           "but it is not among that domain's 40 candidates by stars.")
            else:
                out.append(f"- {r} (v2: {pc['domain']}): no area+kind pair among its topics "
                           f"({', '.join(topics) or 'none recorded'}), or an excluded topic.")
    out += ["", f"New ({len(set(now_sel) - set(prev_sel))}):", ""]
    for r, c in now_sel.items():
        if r not in prev_sel:
            out.append(f"- {r} ({c['domain']}, via {pairs_of(c)}).")
    out.append("")
    return out


def write_report(queries: list[dict], candidates: list[dict], selected: list[dict]) -> str:
    q_dates = sorted({q["fetched_at"][:10] for q in queries})
    pr_dates: dict[str, int] = {}
    for r in {c["repo"]: c for c in candidates}.values():
        pr_dates[r["pr_count_fetched_at"][:10]] = pr_dates.get(r["pr_count_fetched_at"][:10], 0) + 1
    out = [f"# Repository selection by rule ({RULE_VERSION})", "",
           f"Search query dates: {', '.join(q_dates)}. Pull request counts fetched on: "
           + ", ".join(f"{d} ({n})" for d, n in sorted(pr_dates.items()))
           + " (counts from an earlier version are reused from the shared cache). "
           f"Window: {WINDOW_START} to {WINDOW_END} by pull request creation date. "
           f"Keep {MIN_PRS:,}-{MAX_PRS:,} pull requests, a pull request template, and a contributing guide; "
           f"top {PER_DOMAIN_KEEP} per domain by pull requests; a repository counts in the first domain it appears in.",
           "", "## Rule", "", RULE_V3_TEXT, "",
           f"Rule SHA-256 (rule data, text, and queries): `{RULE_SHA256}`; written to RULE.md before the run.", "",
           "| domain | areas | kinds | excluded topics | queries |", "|---|---|---|---|---:|"]
    for d in RULE_V3["domains"]:
        out.append(f"| {d['domain']} | {', '.join(d['areas'])} | {', '.join(d['kinds'])} | "
                   f"{', '.join(d['exclude'] + RULE_V3['global_exclude'])} | {len(d['areas']) * len(d['kinds'])} |")
    out += ["", "## Summary", ""]
    out.append("| domain | candidates | own (first domain) | pass PR count | survivors | selected |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for domain, _ in DOMAINS:
        cs = [c for c in candidates if c["domain"] == domain]
        own = [c for c in cs if c["assigned_domain"] == domain]
        out.append(f"| {domain} | {len(cs)} | {len(own)} | {sum(c['pass_pr_count'] for c in own)} | "
                   f"{sum(c['survivor'] for c in own)} | {sum(c['selected'] for c in own)} |")
    distinct = {c["repo"] for c in candidates}
    out += ["", f"Distinct candidate repositories: {len(distinct)} (of {len(candidates)} domain slots). "
                f"Selected: {len(selected)}. Pull requests in window across the selected list: "
                f"{sum(c['pr_count'] for c in selected):,}.", ""]
    out += ["## Selected", "",
            "| domain | repo | stars | PRs in window | PR template | contributing | via (area+kind) | notes |",
            "|---|---|---:|---:|---|---|---|---|"]
    for c in selected:
        tpl = "; ".join(t["path"] + ("/" if t["type"] == "dir" else "") for t in c["pr_templates"])
        con = "; ".join(t["path"] for t in c["contributing"])
        notes = []
        if c["already_pulled"]:
            notes.append("already pulled")
        if c["archived"]:
            notes.append("archived")
        if c["mirror_url"]:
            notes.append(f"mirror of {c['mirror_url']}")
        if c["template_is_directory_only"]:
            notes.append("template is a directory of %d files" % sum(len(t["files"]) for t in c["pr_templates"]))
        if c["also_in_domains"]:
            notes.append("also in " + ", ".join(c["also_in_domains"]))
        out.append(f"| {c['domain']} | {c['repo']} | {c['stars']:,} | {c['pr_count']:,} | {tpl} | {con} | "
                   f"{pairs_of(c)} | {'; '.join(notes)} |")
    out += ["", "## Changes from v2", ""] + changes_from(OUT / "v2" / "selected.json", candidates, selected)
    present = [r for r in ALREADY_PULLED if any(c["repo"] == r for c in selected)]
    absent = [r for r in ALREADY_PULLED if r not in present]
    out += ["## Overlap with the twelve repositories already pulled", "",
            f"On the list ({len(present)}): {', '.join(present) or 'none'}.", "",
            f"Not on the list ({len(absent)}): {', '.join(absent) or 'none'}.", ""]
    for r in ALREADY_PULLED:
        cs = [c for c in candidates if c["repo"] == r]
        if cs and r in absent:
            c = cs[0]
            why = c["selection_note"] or "; ".join(x for x in c["reasons"] if x != "files not checked")
            out.append(f"- {r}: candidate in {c['domain']} (rank {c['domain_rank_by_stars']} by stars, "
                       f"via {pairs_of(c)}); {why}.")
        elif not cs:
            out.append(f"- {r}: not among any domain's 40 candidates.")
    out += ["", "## Queries", "", "| domain | query | fetched | API total | returned |", "|---|---|---|---:|---:|"]
    for q in queries:
        total = "" if q["total_count"] is None else f"{q['total_count']:,}"
        out.append(f"| {q['domain']} | `{q['query']}` | {q['fetched_at']} | {total} | {q['returned']} |")
    out += ["", "Each domain's candidates are the union of its queries' results (sorted by stars, "
                f"{PER_DOMAIN_CANDIDATES} per query), cut to the {PER_DOMAIN_CANDIDATES} with the most stars. "
                "The API rejects OR between qualifiers, so each area+kind pair is its own query.", ""]
    for domain, _ in DOMAINS:
        out += [f"## {domain}", "", md_table([c for c in candidates if c["domain"] == domain]), ""]
    return "\n".join(out)


def write_rule() -> None:
    """Write RUN/RULE.md (rule text, data, queries, timestamp) before any query of this version."""
    RUN.mkdir(parents=True, exist_ok=True)
    path = RUN / "RULE.md"
    if path.exists():
        sys.exit(f"{path} exists; a version's rule is written once")
    n = sum(len(qs) for _, qs in DOMAINS)
    out = [f"# Repository selection rule {RULE_VERSION}", "",
           f"Written {now_iso()}, before any {RULE_VERSION} query ran. Rule SHA-256 (rule data, text, and "
           f"queries): `{RULE_SHA256}`. The run refuses to start if this hash no longer matches the script.", "",
           "## Rule", "", RULE_V3_TEXT, "",
           "## Why (from the v2 diagnosis)", "",
           "In v2 a star-sorted single-topic query let in popular applications that carry a topic for a "
           "technology they use: immich and coolify (svelte) and gitea (vue) in frontend-frameworks; orca "
           "(runtime) in languages-and-runtimes; volcano (hpc) and burn (scientific-computing) in "
           "scientific-computing; backstage (infrastructure) in systems-and-infrastructure; streamlit "
           "(machine-learning, deep-learning) in ml-frameworks; and, arguably, n8n and gemini-cli (cli) in "
           "developer-tools and metabase (database) and superset (data-engineering) in data-systems. Four of "
           "those carry `self-hosted`. The co-tag requires a second topic that says what the repository is; "
           "the exclusions drop deployable applications and link lists outright.", "",
           "## Domains (in assignment order)", "",
           "| domain | areas | kinds | excluded topics | queries |", "|---|---|---|---|---:|"]
    for d in RULE_V3["domains"]:
        out.append(f"| {d['domain']} | {', '.join(d['areas'])} | {', '.join(d['kinds'])} | "
                   f"{', '.join(d['exclude'] + RULE_V3['global_exclude'])} | {len(d['areas']) * len(d['kinds'])} |")
    out += ["", f"## Queries ({n})", ""]
    for domain, qs in DOMAINS:
        out += [f"- {domain}:"] + [f"  - `{q}`" for q in qs]
    out += ["", "## Rule data", "", "```json", json.dumps(RULE_V3, indent=1), "```", ""]
    path.write_text("\n".join(out))
    print(f"wrote {path} ({n} queries); rule sha256 {RULE_SHA256}", file=sys.stderr)


def main() -> None:
    if "--write-rule" in sys.argv[1:]:
        write_rule()
        return
    rule_md = RUN / "RULE.md"
    if not rule_md.exists() or RULE_SHA256 not in rule_md.read_text():
        sys.exit(f"{rule_md} is missing or does not carry this rule's hash; run --write-rule first")
    for name in ("selected.json", "candidates.json", "REPORT.md"):
        if (RUN / name).exists():
            sys.exit(f"{RUN / name} exists; a version's outputs are never overwritten")
    queries, candidates = domain_candidates()
    seen: dict[str, dict] = {}
    for i, c in enumerate(candidates, 1):
        if c["repo"] in seen:  # same repo under a later domain: copy the checks, no new calls
            src = seen[c["repo"]]
            for k, v in src.items():
                if k not in ("domain", "domain_rank_by_stars", "matched_queries"):
                    c[k] = v
            continue
        check_repo(c)
        seen[c["repo"]] = c
        print(f"[{i}/{len(candidates)}] {c['repo']}: prs={c['pr_count']} survivor={c['survivor']}",
              file=sys.stderr, flush=True)
    selected = select(candidates)
    meta = {"generated_at": now_iso(), "rule_version": RULE_VERSION, "rule_sha256": RULE_SHA256, "rule": RULE_V3,
            "rule_text": RULE_V3_TEXT, "window": [WINDOW_START, WINDOW_END], "min_prs": MIN_PRS,
            "max_prs": MAX_PRS, "per_domain_candidates": PER_DOMAIN_CANDIDATES, "per_domain_keep": PER_DOMAIN_KEEP,
            "author_owners_excluded": AUTHOR_OWNERS, "domains": [d for d, _ in DOMAINS], "queries": queries,
            "already_pulled": ALREADY_PULLED}
    report = write_report(queries, candidates, selected)  # before any file, so a failure writes nothing
    (RUN / "candidates.json").write_text(json.dumps({**meta, "candidates": candidates}, indent=1))
    (RUN / "selected.json").write_text(json.dumps({
        **meta,
        "selected": [{**{k: c[k] for k in ("domain", "repo", "stars", "pr_count", "pr_templates", "contributing",
                                            "archived", "mirror_url", "already_pulled", "also_in_domains",
                                            "template_is_directory_only", "matched_queries")}}
                     for c in selected],
        "already_pulled_on_list": [r for r in ALREADY_PULLED if any(c["repo"] == r for c in selected)],
        "already_pulled_not_on_list": [r for r in ALREADY_PULLED if not any(c["repo"] == r for c in selected)],
    }, indent=1))
    (RUN / "REPORT.md").write_text(report)
    print(f"selected {len(selected)} repositories; wrote {RUN}", file=sys.stderr)


if __name__ == "__main__":
    main()
