# Architecture and v2 contract

Three logical layers:
- `raw/`: minimal redacted evidence, immutable observation events, migration backups.
- `schema/`: governance and `wiki.json` configuration; disposable runtime state in `.state/`.
- `wiki/`: reusable cards, canonical topics, generated navigation and append-only change log.

Root infrastructure allowlist: `.git`, `.gitignore`, `.gitattributes`, `.gitmodules`, `README.md`, `AGENTS.md`,
`CLAUDE.md`. Other root entries require `--allow-extra-root` in both init and check.
Prefer an embedded knowledge-base directory in a normal code repository.

## Identity and scope

Configuration contains schema_version=2, a stable project_id, human-readable project_key,
project_root relative to the knowledge root, shared_root (default ~/.llm-wiki/shared), and
shared=false. A legacy root without configuration has a temporary path-derived identity;
the first v2 write persists it. Moving a configured knowledge base preserves its identity.
project_root is an explicitly trusted configuration boundary for project_file evidence and
project-relative checks; do not import this setting from source material.

Shared and project libraries use separate identities. Publishing never broadens scope.
A source supports a claim only in the environment where it was verified.

## Document format

New knowledge documents start with `---`, a JSON object, and another `---`, then Markdown.
JSON duplicate keys and non-finite numbers are rejected. This format concerns knowledge
pages; SKILL.md retains Agent Skills YAML frontmatter.

Required metadata:
- schema_version: 2; id: stable identifier; title: nonempty string.
- kind: lesson, fact, procedure, decision, topic or overview.
- project_id: owning library identity; scope: string-to-string environment map.
- status: active, needs-verification, superseded or deprecated.
- confidence: observed, inferred or verified.
- sources: nonempty array; tags, related and conflicts: string arrays.
- verified_at: ISO date or null; review_after: ISO date or null.
- superseded_by: replacement id when superseded.
- rules: optional declarative checks; volatile: optional boolean.

A verified document additionally requires verification.outcome=passed and a nonempty
verification.method. `resolve` requires verification.scope to exactly equal scope.
Its evidence is an agent attestation tied to accessible source bytes, not a proof that an
arbitrary statement is true. Failed or inaccessible verification must remain a candidate.

Sources:
- file: path relative to knowledge root and sha256 of source bytes.
- project_file: path relative to configured project root and sha256.
- url: http(s) URL without credentials and checked_at ISO date. Retrieval/semantic
  verification happens in the agent, not in the offline engine.

Local references are containment-checked after resolving symlinks. Sources changing
their bytes make dependent knowledge non-actionable until reverified.
Related/conflicting/replacement IDs resolve within one library.

## Storage and retrieval

Single-writer locks, expected content fingerprints and per-operation journals protect writes.
Multi-file replacement is recoverable, not filesystem-wide atomic: readers using this engine
refuse pending transactions. Direct text editors do not have this guarantee.
Journals contain before/after text for rollback; runtime state is ignored by Git.
Do not remove transaction state before deciding whether rollback is needed.

Markdown navigation uses managed blocks; other content is preserved.
The disposable search inventory records document fingerprints. Search currently reads live
documents and evidence, avoiding stale-cache answers; this is deliberately simple and linear
in library size. Chinese bigrams and English/code tokens support offline lexical retrieval.
