# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Latest published release | Yes |
| Older releases | No |

Security fixes are normally applied to `main` and included in the next appropriate
release. Older releases may not receive backports.

## Reporting a vulnerability

Please do **not** open a public issue, discussion, or pull request containing sensitive
security details.

Email **shiehharry@gmail.com** with a subject such as:

```text
[SECURITY] polish-open-source-prose: brief title
```

Reports are welcome in English or Traditional Chinese. Please include, where applicable:

- the affected commit, tag, file, or component;
- the host and version involved, such as Codex or Claude Code;
- the security impact and the boundary that is crossed;
- minimal, reproducible steps using sanitized inputs;
- relevant logs or output with secrets and private data removed; and
- a suggested mitigation, if you have one.

Use synthetic data and canary values. Do not send real credentials, tokens, private
repository content, personal data, customer data, or destructive payloads. Ask before
sending large or encrypted attachments.

## Response and coordinated disclosure

The maintainer aims to acknowledge a report within five business days and provide an
initial assessment within ten business days. Complex reports may take longer to verify.

Please allow time to investigate and release a fix before publishing technical details.
The maintainer will coordinate disclosure timing with the reporter when practical and
can credit the reporter if requested. This project does not currently offer a bug bounty.

## In scope

Examples of security issues that are in scope include:

- skill instructions or bundled scripts that unexpectedly execute commands, write outside
  intended paths, bypass an explicit approval boundary, or disclose protected data;
- command injection, path traversal, unsafe temporary-file handling, or unsafe file writes
  in validation or installation helpers;
- credential or token leakage through prompts, generated output, logs, error messages,
  fixtures, or reproducible-evidence workflows;
- plugin manifests, packaging, or installation behavior that causes unintended code or
  instructions to run;
- GitHub Actions, release, dependency, or supply-chain weaknesses that can compromise
  contributors or distributed artifacts;
- project-specific prompt or instruction injection with a reproducible security impact;
  and
- dependency vulnerabilities that are directly exploitable through this project.

## Out of scope

The following are generally not security vulnerabilities in this project:

- style, grammar, tone, localization, or editorial disagreements;
- incorrect, low-quality, or over-edited prose without a security impact;
- generic claims about language-model behavior without a project-specific exploit path;
- vulnerabilities solely in Codex, Claude Code, GitHub, or another third-party service;
- attacks that require an already-compromised machine or credential;
- social engineering, spam, denial-of-service, or high-volume testing; and
- scanning or testing repositories, services, accounts, or infrastructure without the
  owner's explicit authorization.

Report vulnerabilities in third-party projects to those projects through their own
security policies. This policy covers only this repository and its distributed artifacts;
it does not authorize security testing of any other repository or system.

## Testing boundaries

Please keep testing local, minimal, and reversible:

- use a local clone, synthetic fixtures, and canary secrets;
- do not access real credentials, provider endpoints, private data, or user accounts;
- do not modify another person's repository, account, or infrastructure;
- do not run destructive, persistent, or high-volume tests; and
- do not publish exploit details before coordinated disclosure.

## Project security boundary

Polish Open-Source Prose is an Agent Skill and validation package. It is not a sandbox,
permission system, or security product. Host permissions, sandboxing, user confirmation,
repository policy, and human review remain necessary.

A useful report should identify the project-specific path from a file, instruction,
manifest, script, or workflow in this repository to a concrete security impact.
