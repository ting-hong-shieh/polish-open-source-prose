# Contributing

Contributions should improve a concrete editorial outcome without weakening factual
fidelity or flattening native voice.

## Before opening a pull request

Open an issue first when proposing:

- a new locale pack;
- a broad rule that affects many passages;
- a change to provenance or watermark guidance;
- a license, governance, or compatibility change.

Small corrections, broken links, and focused test additions can go directly to a pull
request.

## Report an editorial problem

Include:

- the target locale and document surface;
- the original passage;
- the current result, if applicable;
- the expected behavior;
- every fact, qualification, command, identifier, or structure that must survive;
- whether the report is a missed edit or a false positive.

Use text you have permission to redistribute. Remove secrets, private issue content,
personal data, and unpublished product information.

## Add a locale pack

Follow the
[locale pack contract](skills/polish-open-source-prose/references/locale-pack-contract.md).
A proposal needs:

1. A specific BCP 47 locale tag and a clear account of nearby locales it does not
   cover.
2. Evidence from project terminology, official regional translations, public style
   guidance, or stable technical-community usage.
3. Contextual terminology rules rather than a bare replacement list.
4. False-positive guards for structures that are natural in the locale.
5. Balanced forward cases, including passages that should remain unchanged.
6. A native reviewer familiar with technical or open-source writing.
7. Documented limitations and unresolved variants.

Do not create a locale pack by translating the English or `zh-Hant-TW` phrase list.

## Add or change a forward case

Each case in
[forward_cases.json](skills/polish-open-source-prose/tests/forward_cases.json) must
include:

- a stable case ID;
- locale, surface, mode, and focus;
- input and recommended result;
- protected substrings;
- wording that should be removed;
- wording that must not be introduced;
- a short rationale.

A recommended revision may only use facts available in the case. Keep cases that test
normal technical prose; a suite containing only obvious promotional text cannot
measure false positives.

## Preserve project boundaries

This project edits prose. It must not:

- claim to identify AI authorship from style;
- optimize text to evade a detector;
- promise removal of a statistical watermark;
- treat a watermark as cryptographic proof of identity;
- invent product behavior, evidence, experience, or author opinions.

Provenance changes should prefer signed canonical artifacts and state what the
signature does and does not prove.

## Run checks

From the repository root:

```bash
python3 scripts/validate_repo.py
```

If you changed the skill, also run:

```bash
python3 skills/polish-open-source-prose/scripts/validate_skill.py
```

## Pull request checklist

- Keep the pull request focused on one problem or locale.
- Explain the observable problem and why the chosen change is smaller than the
  alternatives.
- Add or update forward cases for behavior changes.
- Confirm that protected strings, links, commands, and markup still pass validation.
- Separate editorial preference from semantic or locale errors.
- List known limitations and any native review still required.

## Licensing

By submitting original work to this repository, you agree to license that contribution
under Apache-2.0. Identify any incorporated third-party material and its license in
the pull request. Do not submit material that cannot be redistributed under compatible
terms.
