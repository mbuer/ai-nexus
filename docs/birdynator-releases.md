# Birdynator releases

A release identifies a reviewed set of code and features. The Git commit is the
exact source identity. A readable version and these notes help a reader understand
what changed; deployment receipts establish which hosts actually installed it.

## Current repository release: `415eda0` — October 12, 2026

The approved read-only inspection confirmed AI Nexus at
`415eda019d056d62c35ab69bda95cf3401201751` with no pending changes. Its local
remote-tracking reference matched; this inspection did not contact GitHub.

This release added the bounded species-history Journal trial:

- Compare species across matched multi-day windows, rather than repeatedly leading
  with activity totals or isolated detections.
- Supply recent topics as editorial context, separately from source evidence.
- Retain exact request, model, prompt and evidence identity for later comparison.
- Present an optional fuller narrative in one reading column, with collapsed
  provenance and no mandatory diversity chart.
- Select trial prompt v3.2 for October 13–19 at 21:00 Pacific; resume baseline v3.0
  on October 20. Acceptance requires a later human decision.

The default model is `gpt-6.1-sol`. Reading publication remains manual. This source
release does not contain the subsequent Utility feedback feature.

## Unreleased source update: HTTPS and personal feedback

Operator results confirm installation on Utility, including successful reading,
sign-in and review collection on Windows and Android. The prepared source has not
been committed or pushed as this release.

- Private-authority HTTPS, local certificate preparation and renewal tooling.
- One personal account with stable reviewer identity across devices.
- An authenticated private queue with append-only review revisions and exact report
  identity; saving and history remain protected while reading stays open.
- Visible sign-in status, safer browser retry handling and symmetrical account spacing.
- Smaller reading exports while retaining complete structured provenance.

AI Nexus SQL import, feedback return transport, off-VM queue backup cadence and
long-term learning automation remain incomplete. The SQL draft stays under
`proposals/`, outside automatic migrations. Reviews do not modify memory or prompts.

See [feedback](journal-feedback.md) for the design and remaining release gates.

## Version policy proposed for the next release

Keep Birdynator in the AI Nexus repository. Assign the next approved integrated
release a human-readable `MAJOR.MINOR.PATCH` version and a namespaced Git tag
`birdynator-vMAJOR.MINOR.PATCH`; record its commit, features, upgrade steps and
known limitations here. No numeric version or tag has been assigned by this work.

Use a minor increment for a compatible feature, a patch for a compatible fix and
a major increment for a breaking interface or required operator migration. Combine
related code, tests and documentation in one coherent commit. A tag identifies
source; it does not imply installation, prompt acceptance or rollback completion.

Keep prompt, evidence, report and feedback-schema versions independent. Store the
actual model and exact report identity with each analysis/review. Container tag
`:1` is a mutable operational name, not a Birdynator release number; retain image
identity and deployment receipts when reconstructing a running system.
