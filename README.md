<p align="center">
  <img src="docs/assets/readme-banner.svg" alt="Polish Open-Source Prose wordmark — edit public project prose without losing facts or voice" width="100%">
</p>

<p align="center">
  <a href="README.zh-Hant-TW.md">繁體中文</a>
  ·
  <a href="#quick-start">Quick start</a>
  ·
  <a href="#how-we-tested-it">How we tested it</a>
  ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <a href="https://github.com/ting-hong-shieh/polish-open-source-prose/actions/workflows/validate.yml"><img src="https://github.com/ting-hong-shieh/polish-open-source-prose/actions/workflows/validate.yml/badge.svg?branch=main" alt="Validation status"></a>
  <img src="docs/assets/logo-badge.svg" alt="Polish Open-Source Prose">
  <img src="https://img.shields.io/badge/forward_cases-49-0f766e?style=flat-square" alt="49 forward cases">
  <img src="https://img.shields.io/badge/license-Apache--2.0-2563eb?style=flat-square" alt="Apache-2.0 license">
</p>

Ask a model to polish a paragraph and it will change something, even when nothing was
wrong. In our tests, current models already cut hype on their own. They also turned
"This fix addresses" into "This PR fixes", added "so a retry is safe" to a code comment,
and decided that "multilingual codebase" meant "more than one programming language".

This skill is the brake for that. It tells the agent to return clear text unchanged,
keep exact content exact, and ask for missing facts instead of inventing them. It does
not try to make prose sound more human; current models already do that.

It is an [Agent Skill](https://agentskills.io) for README files, documentation, release
notes, changelogs, pull requests, issues, code comments, UI copy, and error messages,
and it runs on Claude Code and Codex.

## What it prevents

Each example below shows the input, what Claude Opus 5.5 returned without the skill,
and what it returned with the skill. All three come from the
[test cases](skills/polish-open-source-prose/tests/forward_cases.json); see
[How we tested it](#how-we-tested-it).

### A scoped claim stays scoped

> This fix addresses the cache-key collision reported in #512. It does not cover the
> stale-entry eviction discussed in #530.

| Without the skill | With the skill |
| --- | --- |
| This PR **fixes** the cache-key collision reported in #512. It does not **address** the stale-entry eviction discussed in #530. | Unchanged. |

"Addresses" leaves room for a partial fix. "Fixes" tells the reviewer the whole issue
is closed, which the author did not say.

### A code comment does not gain a claim

```rust
// Retry once on ECONNRESET: the upstream load balancer closes idle keep-alive
// connections after 60 s without sending FIN, so the first write on a reused
// connection can fail even though the request never reached the server.
```

In one of the two runs without the skill, the last line became "The request never
reached the server, so a retry is safe." The original says why the write fails. It does
not say that retrying is safe in general. With the skill, the comment came back
unchanged in both runs.

### A missing fact is asked for, not invented

> PolyglotGuard is a powerful, next-generation solution that seamlessly protects your
> multilingual codebase across today's rapidly evolving ecosystem.

| Without the skill | With the skill |
| --- | --- |
| PolyglotGuard protects codebases that use more than one programming language. | PolyglotGuard protects multilingual codebases. |

Both versions drop the hype. Without the skill, the model also picked a meaning for
"multilingual" that the source never states. With the skill, it kept the sentence to
what is known, and in one run asked afterwards: "What does "multilingual" mean here:
several programming languages, or several human languages (i18n)?"

## What it does and does not do

The skill:

- returns text unchanged when it is already clear and fits its surface;
- keeps numbers, versions, conditions, negation, scope, commands, links, identifiers,
  quotations, license and policy text, Markdown structure, and deliberate voice exact;
- does not add metrics, test results, commit hashes, or behavior the source does not
  contain, and asks for missing facts after the revision;
- does not let "all tests pass" or "completely fixed" stand without a command, commit,
  and scope, and drops or asks for evidence behind claims such as "robust" or "scales
  better".

It does not:

- make prose sound more human, which current models already do without it;
- decide whether a person or a model wrote a passage, or help text evade an AI
  detector;
- remove a statistical watermark or treat one as proof of identity; for authorship, it
  recommends a signed commit or file;
- replace legal, security, or domain review;
- fix most of what reviewers object to in real pull requests, which usually needs facts
  only the author has (see [How we tested it](#how-we-tested-it)).

## Quick start

### Install with Claude Code

Add this repository as a plugin marketplace, then install the plugin:

```text
/plugin marketplace add ting-hong-shieh/polish-open-source-prose
/plugin install polish-open-source-prose
```

To install the skill without the plugin system, copy the directory instead:

```bash
git clone https://github.com/ting-hong-shieh/polish-open-source-prose.git
cp -r polish-open-source-prose/skills/polish-open-source-prose ~/.claude/skills/
```

Use `.claude/skills/` in a project instead of `~/.claude/skills/` to scope the skill to
that repository.

### Install with Codex

Invoke `$skill-installer` and ask:

> Install the `polish-open-source-prose` skill from this repository's
> `skills/polish-open-source-prose` directory:
> `https://github.com/ting-hong-shieh/polish-open-source-prose/tree/main/skills/polish-open-source-prose`

You can also use the skill folder directly during local development:

```text
skills/polish-open-source-prose
```

### Use it

Claude Code loads the skill when a request matches its description. To invoke it
directly, use `/polish-open-source-prose` in Claude Code or `$polish-open-source-prose`
in Codex. For example:

```text
Polish this PR description. Leave anything that is already clear.

Check this release note for claims the changes do not support.

Review this README section and list only edits that fix a concrete problem.
```

## How we tested it

We gave short passages to seven model configurations with an instruction to revise
them: Claude Opus 5.5, Opus 4.6, and Sonnet 5.5 in Claude Code, and GPT-6.1 Sol, GPT-6
Astra at high and low effort, and GPT-6 Luna in Codex. Each passage ran under five
conditions:

- **No skill**: the instruction alone.
- **One sentence**: the instruction, preceded by "If the text is already clear and fits
  its surface, returning it unchanged is a valid answer."
- **Three sentences**: the instruction, preceded by the
  [short instruction](#without-installing-the-skill) below.
- **v0.1.0** and **v0.2.0**: the instruction, with that version of the skill.

There were three sets of passages:

- **Development set**: the 49 [test cases](skills/polish-open-source-prose/tests/forward_cases.json)
  the skill was built against.
- **A1**: 24 new cases, 16 of them in English, written after v0.2.0 was released and
  frozen before any run. Some passages are already fine and should come back unchanged;
  the rest have a problem to fix.
- **A2**: 21 real pull request titles and descriptions from Apache Airflow, Arrow,
  DataFusion, and CPython, as they stood before a reviewer criticized them. The text
  stays private; the URLs and a hash are in
  [`evals/heldout/a2_manifest.json`](evals/heldout/a2_manifest.json).

Every output was checked for specific strings, and Claude Opus 5.5 and GPT-6.1 Sol
graded the A1 and A2 outputs without knowing which model or condition produced them. A
*clean fix* scores how well an output fixed the problem, counting it only when the output
neither added a fact nor damaged text that was needed. The method and every result are
in the [report](docs/report/report.pdf).

Averages over the seven configurations; a range shows the two judges:

| | No skill | One sentence | Three sentences | v0.1.0 | v0.2.0 |
| --- | --- | --- | --- | --- | --- |
| A1 English: clear passages left unchanged | 4% | 52% | 96% | 40% | 96% |
| A1 English: clean fix (0 to 1) | 0.42 | 0.42–0.43 | 0.26–0.28 | 0.63–0.65 | 0.67–0.69 |
| A2: clean fix (0 to 1) | 0.12–0.15 | 0.15–0.18 | 0.07–0.10 | 0.22–0.25 | 0.18–0.19 |
| A2: rewrites that added a fact | 21–38% | 9–22% | 0–5% | 8–18% | 0–1% |

What this shows:

- Without guidance, every model rewrote almost every passage that was already fine.
- A short instruction removes most of those edits. The three-sentence instruction kept
  clear text as well as v0.2.0 did. If restraint is all you need, it may be enough.
- The three-sentence instruction also left unsupported claims in place, such as "3x
  faster" with no benchmark. v0.2.0 fixed those far more often. The skill adds the
  second half: which problems are worth an edit.
- On real pull requests, no condition cleanly fixed more than about a quarter of what
  reviewers objected to; most critiques needed facts only the author had. v0.2.0 mostly
  avoided making things worse. Without an instruction, rewrites often added facts, and
  in 10 of 70 outputs changed or deleted the author's `Generated-by:` disclosure line.
  With v0.2.0, none did.
- v0.1.0 fixed somewhat more of the real critiques than v0.2.0, especially unclear
  descriptions and misleading titles. The difference is not significant on 21 cases.
- In Claude Code, a v0.2.0 run cost 2.5 to 3.3 times as much as a run without it.
  GPT-6 Luna at max effort ignored the first rule on about half the clear passages.

What it does not show:

- We wrote the development set and A1. A1 was drafted with Claude Opus 5.5, which is
  also a tested model and a judge.
- A2 has 21 English pull requests from four projects.
- String checks miss good edits worded differently, and the judges are models too.
- Claude configurations ran twice and Codex configurations once, and the short
  instructions were written once, in English.

<details>
<summary>Development set results (21 English cases, three models)</summary>

These ran before the held-out sets, on three models: Claude Opus 5.5 in Claude Code
twice per condition, and GPT-6.1 Sol and GPT-6 Astra in Codex once. A cell with two
numbers shows two runs. While building v0.2.0 we corrected the expected results of
several cases that need an edit, so v0.2.0 has a home advantage on the second table;
treat these numbers as a regression check.

**Passages that should stay unchanged (8)**

| Model | No skill | One sentence | Three sentences | v0.1.0 | v0.2.0 |
| --- | --- | --- | --- | --- | --- |
| Claude Opus 5.5 | 0, 2 | 5, 6 | 7, 7 | 5, 6 | 8, 8 |
| GPT-6.1 Sol | 0 | 3 | 7 | 1 | 8 |
| GPT-6 Astra | 0 | 3 | 6 | 1 | 8 |

**Passages that need an edit (11)**

| Model | No skill | One sentence | Three sentences | v0.1.0 | v0.2.0 |
| --- | --- | --- | --- | --- | --- |
| Claude Opus 5.5 | 8, 7 | 8, 7 | 5, 5 | 6, 7 | 10, 10 |
| GPT-6.1 Sol | 8 | 5 | 2 | 8 | 10 |
| GPT-6 Astra | 6 | 7 | 4 | 8 | 10 |

The remaining two cases expect the model to ask for missing facts instead of editing; a
word check cannot score that, so they are left out.

</details>

### Without installing the skill

If you only want a model to stop rewriting text that was fine, put this before your
request:

```text
Polish this text only where there is a concrete problem. Leave already-clear text
unchanged. Preserve facts, scope, conditions, negation, commands, links, quotations,
and author voice. Do not invent missing facts.
```

Expect it to skip some edits that are needed.

## Languages

The rules in [`SKILL.md`](skills/polish-open-source-prose/SKILL.md) apply to any
language. Traditional Chinese for Taiwan (`zh-Hant-TW`) has an extra layer for word
choices that depend on context; it is described in the
[Chinese README](README.zh-Hant-TW.md). To add another language, follow the
[locale pack contract](docs/locale-pack-contract.md).

## Development

Run all repository checks:

```bash
python3 scripts/validate_repo.py
```

Run the skill checks directly:

```bash
python3 skills/polish-open-source-prose/scripts/validate_skill.py
```

These checks are structural. They confirm that every test case is well formed, that
protected words appear in both the input and the expected result, and that links
resolve. They do not run a model.

<details>
<summary><strong>Repository layout</strong></summary>

```text
.
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .codex-plugin/plugin.json
├── docs/
│   ├── assets/
│   └── locale-pack-contract.md
├── scripts/validate_repo.py
└── skills/
    └── polish-open-source-prose/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/
        ├── scripts/
        └── tests/
```

Each host reads its own manifest directory and the shared `skills/` tree, so adding an
agent platform does not fork the editorial content. Repository documentation stays
outside the skill directory so it is not loaded as agent instructions.

</details>

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a new rule or language. The
most useful contributions are:

- a passage the skill changed when it should have left it alone;
- a passage where it kept an unsupported claim or invented a fact;
- test cases from real project text you can redistribute;
- native review of a language layer.

## Background

This project started from the ideas in [stop-slop](https://github.com/hardikpandya/stop-slop)
and several Taiwan "humanizer" projects:
[speak-human-tw](https://github.com/Raymondhou0917/speak-human-tw),
[Humanizer-zh-TW](https://github.com/kevintsai1202/Humanizer-zh-TW),
[humanizer-zh-tw](https://github.com/nagameTW/humanizer-zh-tw), and
[Humanizer-zh-TW-Pro](https://github.com/slivenred/humanizer-zh-TW-Pro). Testing showed
that current models already do most of that work, so v0.2.0 removed the phrase lists
and kept only the rules that stop over-editing. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for what earlier versions included.

## License

Apache-2.0. See [LICENSE](LICENSE).
