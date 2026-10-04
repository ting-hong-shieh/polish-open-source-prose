# Text provenance, SynthID, and author identity

Use this guidance when a user asks whether prose can be made “not AI,” whether a
watermark can carry an identity, or how to prove that a public artifact came from a
particular GitHub account.

## Separate three different goals

| Goal | Appropriate method | What it does not prove |
| --- | --- | --- |
| Improve clarity and voice | Editorial revision with semantic checks | Whether a human or model wrote the text |
| Mark model output | A generation-time watermark such as SynthID Text | The real-world identity of the author |
| Prove control of an identity | A cryptographic signature or attestation | That no AI assisted the writing |

Do not collapse these goals into one detector score or “humanized” label.

## What SynthID Text can do

SynthID Text modifies token probabilities while a language model is generating text,
then detects the resulting statistical signal. Ordinary editing after generation does
not add a valid watermark.

The watermark key selects a watermarking scheme; it is not an arbitrary text payload.
A GitHub username therefore cannot be embedded and read back as metadata, and a key
derived from a public username could be copied. Translation or substantial rewriting
can also weaken the signal. Treat any per-author configuration as an experimental
marker, never as an authentication system.

- [Google DeepMind: SynthID](https://deepmind.google/models/synthid/)
- [Google DeepMind SynthID Text reference implementation](https://github.com/google-deepmind/synthid-text)

## Recommended GitHub authorship path

Put the canonical text in a repository and sign the commit or tag with an SSH, GPG, or
S/MIME key connected to the author's GitHub account, so GitHub shows a `Verified`
status
([About commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification)).
For a file distributed outside Git, publish a detached signature or Sigstore bundle
next to it
([Sigstore: Signing Blobs](https://docs.sigstore.dev/cosign/signing/signing_with_blobs/)).

A signature proves that the key approved a specific, byte-stable artifact. It does not
prove that the prose was written without tools or collaborators.

For an issue or pull-request comment that needs durable authorship evidence, publish
the canonical text as a signed commit or file and link it from the comment. Do not
describe an invisible text watermark as proof that a comment belongs to a username.

## Editorial response

When asked to “remove AI”:

1. Ask what concrete problem matters: vague claims, hype, wrong locale, or lost voice.
2. Edit that problem under the rules in [../SKILL.md](../SKILL.md).
3. Do not optimize against a detector or promise that a watermark is gone.
4. If the real goal is attribution, recommend a signed canonical artifact.
