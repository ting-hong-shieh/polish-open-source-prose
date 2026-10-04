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

## What it changes

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
- replace legal, security, or domain review.

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

The repository has 49 short test cases taken from the kinds of text open-source
projects publish: README paragraphs, pull request descriptions, review replies, commit
messages, and code comments. Each case records the input and the expected result. Some
passages are already fine and should come back unchanged; the rest need an edit.

We gave each passage to three models with an instruction to revise it: once without the
skill, once with v0.1.0, and once with this version. Claude Opus 5.5 ran in Claude Code,
twice per version. GPT-6.1 Sol and GPT-6 Astra ran in Codex, once per version. Each
model got the same instruction in every run, but the wording differed a little between
models, so compare the columns, not the rows.

Results for the 21 English cases. A cell with two numbers shows two runs.

**Passages that should stay unchanged (8)**

| Model | No skill | v0.1.0 | v0.2.0 |
| --- | --- | --- | --- |
| Claude Opus 5.5 | 0, 2 | 5, 6 | 8, 8 |
| GPT-6.1 Sol | 0 | 1 | 8 |
| GPT-6 Astra | 0 | 1 | 8 |

**Passages that need an edit (11)**

| Model | No skill | v0.1.0 | v0.2.0 |
| --- | --- | --- | --- |
| Claude Opus 5.5 | 8, 7 | 6, 7 | 10, 10 |
| GPT-6.1 Sol | 8 | 8 | 10 |
| GPT-6 Astra | 6 | 8 | 10 |

The remaining two cases expect the model to ask for missing facts instead of editing; a
word check cannot score that, so they are left out.

What this shows: without the skill, every model rewrote almost every passage that was
already fine. With v0.2.0, all three left them alone. On passages that needed an edit,
v0.2.0 passed a few more, but with 11 cases the difference is small.

What it does not show: we wrote the cases and the expected results ourselves, the
scoring checks for specific words rather than judging quality, and each model ran only
once or twice. The last rule in `SKILL.md`, about keeping facts that sit inside a
promotional sentence, was added after these runs and was checked only on the case that
needed it and on the unchanged-passage cases. Treat these numbers as a regression
check, not a benchmark.

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

## License and acknowledgments

Original contributions are licensed under Apache-2.0. Material derived from
`hardikpandya/stop-slop` remains under its MIT license. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
[LICENSE.stop-slop](skills/polish-open-source-prose/LICENSE.stop-slop).

The design was informed by public work from
[stop-slop](https://github.com/hardikpandya/stop-slop),
[speak-human-tw](https://github.com/Raymondhou0917/speak-human-tw),
[Humanizer-zh-TW](https://github.com/kevintsai1202/Humanizer-zh-TW),
[humanizer-zh-tw](https://github.com/nagameTW/humanizer-zh-tw), and
[Humanizer-zh-TW-Pro](https://github.com/slivenred/humanizer-zh-TW-Pro).
