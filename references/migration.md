# Migration Guide

Use this guide when an agent already has scattered knowledge, old memory, notes, documents, or exports.

## Process

1. Inventory available material before writing summaries.
2. Copy or record source material under `raw/`.
3. Capture unpromoted observations under `raw/memory/` when they come from sessions or agent memory.
4. Distill narrow reusable findings into `wiki/cards/`.
5. Extract only verified durable knowledge into canonical `wiki/` topic pages.
6. Move behavior rules, project conventions, and safety constraints into `schema/`.
7. Update `wiki/index.md` and append a dated entry to `wiki/log.md`.
8. Run `scripts/check_llm_wiki.py <root>`.

## What Belongs In Wiki

- Stable environment facts and path conventions.
- API contracts, schemas, interfaces, and command entrypoints.
- Operational procedures and verified recovery steps.
- Business rules and user preferences that affect future work.
- Root causes, failed approaches, and validation evidence.
- Known permission, sandbox, deployment, or production boundaries.

## What Belongs In Cards

- One verified or reusable pitfall.
- One command pattern.
- One environment rule with limited scope.
- One recurring user or project preference.
- One decision that may later become part of a topic page.

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
