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
  <img src="https://img.shields.io/badge/forward_cases-28-0f766e?style=flat-square" alt="28 forward cases">
  <img src="https://img.shields.io/badge/license-Apache--2.0-2563eb?style=flat-square" alt="Apache-2.0 license">
</p>

> A Codex skill for editing README files, documentation, release notes, contribution
> guides, PRs, issues, UI copy, error messages, and prompts—without treating a
> blacklist or detector score as a style guide.

<table>
  <tr>
    <td width="33%">
      <strong>Meaning stays intact</strong><br>
      Protect facts, numbers, versions, conditions, negation, attribution, causality,
      commands, links, quotations, and markup.
    </td>
    <td width="33%">
      <strong>Edits fit the surface</strong><br>
      Apply different standards to a README, tutorial, PR, release note, error message,
      or policy document.
    </td>
    <td width="33%">
      <strong>Locales stay specific</strong><br>
      Use regional terminology and false-positive guards instead of a universal
      replacement list.
    </td>
  </tr>
</table>

## Quick start

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

```text
$polish-open-source-prose
```

Try one of these requests:

```text
Audit this README and propose only evidence-backed edits.

Localize these release notes for zh-Hant-TW without changing product behavior.

Review this PR description for unsupported claims and lost qualifications.
```

## How it works

1. **Establish the source of truth.** Inspect code, tests, configuration, and project
   terminology before trusting promotional copy.
2. **Protect semantic constraints.** Lock facts, qualifications, identifiers,
   quotations, legal text, commands, links, and markup.
3. **Diagnose concrete costs.** Revise vagueness, unsupported claims, missing actors,
   broken logic, repeated canned structures, and surface or locale mismatches.
4. **Run a semantic diff.** Compare subjects, numbers, versions, conditions, negation,
   attribution, causality, and ordered steps before delivery.

The skill leaves clear, specific, voice-appropriate prose alone. Passive voice,
parallel lists, fragments, questions, dashes, and polished sentences are not automatic
defects.

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
| English | Core guidance | Open-source editorial signals and surface rules |
| Chinese | Core guidance | Chinese editing signals and semantic safeguards |
| `zh-Hant-TW` | Dedicated locale pack | Taiwan terminology, punctuation, register, and forward cases |
| Other locales | Foundation only | Shared fidelity workflow; native pack and review still required |

The
[locale pack contract](skills/polish-open-source-prose/references/locale-pack-contract.md)
defines the evidence, terminology, false-positive, surface, and test requirements for
adding a language-and-region target. It is also designed to become a policy layer for
a future PolyglotGuard checker.

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

The current corpus contains 28 forward specifications: 11 cases that should remain
unchanged and 17 that should be revised or answered with provenance guidance.
Structural checks catch protected-token drift and corpus errors; native review is
still required to judge real project prose.

<details>
<summary><strong>Repository layout</strong></summary>

```text
.
├── .codex-plugin/plugin.json
├── docs/assets/
├── scripts/validate_repo.py
└── skills/
    └── polish-open-source-prose/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/
        ├── scripts/
        └── tests/
```

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
