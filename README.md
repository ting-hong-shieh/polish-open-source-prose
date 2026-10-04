<p align="center">
  <img src="docs/assets/readme-banner.svg" alt="Polish Open-Source Prose wordmark — edit public project prose without losing facts or voice" width="100%">
</p>

<p align="center">
  <a href="README.zh-Hant-TW.md">繁體中文</a>
  ·
  <a href="#quick-start">Quick start</a>
  ·
  <a href="#locale-support">Locale support</a>
  ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <a href="https://github.com/ting-hong-shieh/polish-open-source-prose/actions/workflows/validate.yml"><img src="https://github.com/ting-hong-shieh/polish-open-source-prose/actions/workflows/validate.yml/badge.svg?branch=main" alt="Validation status"></a>
  <img src="docs/assets/logo-badge.svg" alt="Polish Open-Source Prose">
  <img src="https://img.shields.io/badge/locale-zh--Hant--TW-4338ca?style=flat-square" alt="zh-Hant-TW locale pack">
  <img src="https://img.shields.io/badge/forward_cases-49-0f766e?style=flat-square" alt="49 forward cases">
  <img src="https://img.shields.io/badge/license-Apache--2.0-2563eb?style=flat-square" alt="Apache-2.0 license">
</p>

> An agent skill for editing open-source prose without making it worse. It leaves text
> that is already clear alone, keeps facts, commands, quotations, licenses, and the
> author's voice exact, and does not fill gaps with facts nobody supplied. Includes a
> Traditional Chinese (Taiwan) locale layer. Runs on Claude Code and Codex.

<table>
  <tr>
    <td width="33%">
      <strong>Clear text stays as written</strong><br>
      A request to polish does not oblige an edit. Text that is already clear comes
      back unchanged.
    </td>
    <td width="33%">
      <strong>Exact content stays exact</strong><br>
      Numbers, conditions, negation, commands, links, quotations, licenses, and
      deliberate voice are not rewritten.
    </td>
    <td width="33%">
      <strong>No invented facts</strong><br>
      Missing details become questions for the author, not made-up metrics, commits,
      or test results.
    </td>
  </tr>
</table>

## Quick start

The skill directory follows the [Agent Skills](https://agentskills.io) format, so the
same files work in Claude Code and Codex.

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

### Invoke the skill

Claude Code loads the skill automatically when a request matches its description. To
invoke it directly:

```text
/polish-open-source-prose
```

In Codex:

```text
$polish-open-source-prose
```

Try one of these requests:

```text
Audit this README and propose only evidence-backed edits.

Localize these release notes for zh-Hant-TW without changing product behavior.

Review this PR description for unsupported claims and lost qualifications.
```

## Before and after

These examples come from the
[forward-case corpus](skills/polish-open-source-prose/tests/forward_cases.json).
They show the three decisions the skill makes most often.

### Leave clear technical prose unchanged

**Surface:** README · **Mode:** keep

> The checker reads `.polyglotguard.yml`, then groups files by locale. Without a config file it falls back to built-in rules but does not create one automatically.

The paragraph names the configuration file, processing order, fallback, and negative
guarantee. Rewriting it would risk losing a constraint without adding clarity, so the
expected output is the input.

### Keep the author's voice

**Surface:** pull request · **Locale:** `zh-Hant-TW` · **Mode:** keep

> 這個 bug 真的很鬧：只有週一、locale 是 `zh-Hant-TW` 時才會出現。我先補回歸測試。

In evaluation runs without the skill, models rewrote 「真的很鬧」 as 「很難重現」
or dropped the first person. The condition and the next step are already clear, so the expected output is
the input.

### Remove unsupported claims without inventing replacements

**Surface:** pull request · **Mode:** rewrite

Before:

> This groundbreaking fix completely resolves the multimodal content loss that has plagued users. The decoder now seamlessly handles image and document blocks, delivering a robust and comprehensive solution for all tool-result scenarios.

After:

> This fix addresses the multimodal content loss in tool results. The decoder now handles image and document blocks.

The input does not name the provider, the block format, or how blocks move between
messages, so the revision does not either. If those details matter, the skill asks
the author for them after the revision.

These are expected outputs from a fixed corpus, not a promise of identical wording on
every repository.

## How it works

1. **Decide whether to edit at all.** Clear, specific text that fits its surface comes
   back unchanged.
2. **Protect what must stay exact.** Facts, qualifiers, identifiers, commands, links,
   quotations, licenses, policy text, markup, and deliberate voice.
3. **Do not add facts.** Remove or narrow unsupported claims, and ask for missing
   details instead of filling them in.
4. **Edit only where there is a concrete cost**, with the smallest change, and compare
   the result with the source before delivery.

Passive voice, parallel lists, fragments, questions, dashes, and polished sentences
are not automatic defects.

## What it protects

| Area | Examples |
| --- | --- |
| Meaning | Subjects, scope, comparisons, conditions, exceptions, uncertainty |
| Evidence | Numbers, dates, versions, attribution, causal claims |
| Technical text | Commands, flags, APIs, identifiers, paths, URLs, error strings |
| Quoted and governed text | Quotations, citations, licenses, policies, security steps |
| Structure | Headings, anchors, tables, lists, code fences, placeholders, frontmatter |
| Voice | Deliberate humor, community terms, register, and first-person stance |

## Locale support

| Locale | Status | Coverage |
| --- | --- | --- |
| Any | Core rules | The fidelity and edit rules in `SKILL.md` |
| `zh-Hant-TW` | Locale layer | Context-dependent terms, punctuation, legal text, false-positive guards, forward cases |
| Other locales | Core rules only | A native locale pack and review are still required |

The [locale pack contract](docs/locale-pack-contract.md) defines what a new
language-and-region pack must contain and how it is tested.

## Boundaries

This project does not:

- determine whether a human or model wrote a passage;
- optimize prose to evade an AI detector;
- promise removal of a statistical watermark;
- invent metrics, product behavior, user stories, opinions, or personal experience;
- claim native support for a locale without a reviewed locale pack;
- replace legal, security, or domain review.

For authorship provenance, the skill recommends a signed canonical artifact rather
than treating writing style or a statistical watermark as proof of identity.

## Validation

Run all repository checks:

```bash
python3 scripts/validate_repo.py
```

Run the skill checks directly:

```bash
python3 skills/polish-open-source-prose/scripts/validate_skill.py
```

The current corpus contains 49 forward specifications: 19 cases that should remain
unchanged and 30 that should be revised, audited, or answered with provenance guidance.
Structural checks catch protected-token drift and corpus errors; native review is
still required to judge real project prose.

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
agent platform does not fork the editorial content.

Repository documentation stays outside the skill directory so it is not loaded as
agent instructions.

</details>

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a broad editorial rule or new
locale. Particularly useful contributions include:

- false-positive reports;
- missing semantic safeguards;
- contextual regional terminology;
- examples that can be redistributed;
- balanced change/keep forward cases;
- native review of locale packs.

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
