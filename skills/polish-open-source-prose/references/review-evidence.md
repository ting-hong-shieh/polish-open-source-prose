# Review evidence: proactive claims, snapshots, and experiments

Use this guidance before publishing public OSS prose that contains a quantitative,
absolute, causal, or guarantee-like claim, and whenever a PR or issue follow-up
requests a snapshot, trace, benchmark, test result, or before/after comparison. The
goal is a reviewer-reproducible artifact, not a reassuring summary.

## Trigger before a reviewer asks

Build evidence before publication when text includes or implies:

- counts, percentages, coverage, benchmark results, duration, memory, tolerance, or a
  version/platform range;
- `all`, `every`, `exactly`, `only`, `none`, `complete`, or `fully`;
- `guarantee`, `always`, `never`, `no behavior change`, or `CI is unaffected`;
- “works in serial and parallel,” “each fix was reverted independently,” “all tests
  pass,” or another completeness claim.

The trigger does not mean the claim is wrong. It means the claim must be traceable to
current evidence.

## Claim–Evidence Matrix

For each triggered claim, record:

1. **Claim** — The exact statement being prepared for publication.
2. **Evidence** — Literal command, CI job, code/test/configuration location, raw output,
   or pinned external reference.
3. **State** — Exact head commit and, when comparative, the base/reference commit.
4. **Scope** — Configurations, behaviors, inputs, platforms, and exclusions.
5. **Status** — `VERIFIED`, `PARTIAL`, or `UNSUPPORTED`.
6. **Publication text** — The exact bounded statement that the evidence permits.

Resolve the status as follows:

- **VERIFIED:** keep the statement with its scope and current-head identity.
- **PARTIAL:** narrow it and name what was not tested.
- **UNSUPPORTED:** remove it or state the uncertainty. Do not make it sound more
  credible through style alone.

```markdown
| Claim | Evidence | Head | Scope | Status | Publication text |
| --- | --- | --- | --- | --- | --- |
| `<claim>` | `<command/CI/artifact>` | `<sha>` | `<covered and excluded>` | VERIFIED / PARTIAL / UNSUPPORTED | `<bounded wording>` |
```

## Evidence packet

For a requested snapshot, trace, benchmark, or comparison, provide these fields,
omitting only fields that genuinely do not apply. State what is unavailable instead of
filling a gap with an inference.

1. **State** — Give the exact base and head commit. Say which commit each result
   represents.
2. **Reproduction** — Give the literal command, relevant test path, fixture or input,
   configuration, seed when applicable, environment, and whether a provider, network,
   clock, or other external service was exercised.
3. **Capture** — Show or link the raw trace, JSON, log, screenshot, or numerical output
   before summarizing it. For snapshots, capture both states through the same path.
4. **Comparison** — Name each quantity, unit, expected value or source, error metric,
   and tolerance. Explain whether the reference is an external measurement, an upstream
   implementation, or a deterministic regression value.
5. **Scope and status** — State the configurations and behaviors covered, exclusions,
   repeatability or known variability, and the final-head test or CI result. Do not use
   a result from an earlier commit to vouch for a later change.
6. **Decision** — Answer the review request directly: what is added now, what is
   deferred, why, and which issue or follow-up owns deferred work.

## Classify the experiment

- **External validation:** compare against an observed measurement or a pinned external
  implementation. Cite its identity and conditions; do not call one matching output a
  complete model validation.
- **Deterministic regression:** pin the output of a defined execution path so future
  changes are detectable. It protects that path; it is not an independent proof that the
  output is physically or externally correct.
- **No usable reference:** report the missing evidence and avoid adding an assertion
  merely because a reviewer named another metric.

## Compact response template

```markdown
State: before `<base>`; after `<head>`.
Reproduction: `<command>` using `<fixture/config>` on `<environment>`;
`<external dependency>` was <used/not used>.
Capture: <raw before/after output or artifact link>.
Comparison: `<metric>` (<unit>) is compared with `<reference>` using `<error metric>`
and `<tolerance>`; this is <external validation/deterministic regression>.
Scope: covers <behaviors/configurations>; excludes <behaviors/configurations>.
Status: `<final-head command or CI job>` <passed/failed/is pending> at `<head>`.
Decision: add <item> now; defer <item> to <issue/reason>.
```

Avoid saying “all tests pass,” “fully validated,” “accepted,” or another broad closure
unless the exact command or CI state, current commit, scope, and review decision support
that claim.
