# Migration Guide

Use this guide when an agent already has scattered knowledge, old memory, notes, documents, or exports.

## Process

1. Inventory available material before writing summaries.
2. Copy or record source material under `raw/`.
3. Extract only durable knowledge into `wiki/`.
4. Move behavior rules, project conventions, and safety constraints into `schema/`.
5. Update `wiki/index.md` and append a dated entry to `wiki/log.md`.
6. Run `scripts/check_llm_wiki.py <root>`.

## What Belongs In Wiki

- Stable environment facts and path conventions.
- API contracts, schemas, interfaces, and command entrypoints.
- Operational procedures and verified recovery steps.
- Business rules and user preferences that affect future work.
- Root causes, failed approaches, and validation evidence.
- Known permission, sandbox, deployment, or production boundaries.

## What To Exclude

- Chat filler and task negotiation.
- Long command logs unless the log itself is the evidence.
- Unverified guesses.
- Full source files copied into wiki pages.
- Secrets, credentials, cookies, private keys, or plaintext connection strings.

## Provenance

Every important wiki page should identify where its facts came from. Use short source references such as:

- `Source: raw/chats/2026-06-29-session.md`
- `Source: raw/incidents/payment-timeout-2026-06.md`
- `Verified by: command output in raw/ops/check-2026-06-29.txt`

If a source cannot be checked, mark the conclusion as `needs-verification`.
