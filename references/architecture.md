# LLM Wiki Architecture

Use a three-layer structure to keep agent knowledge simple, traceable, and safe.

## Layers

- `raw/`: source material. Store imported chats, notes, exports, incident logs, command outputs, documents, and snapshots here. Do not edit raw material to make a conclusion look cleaner; add a redacted copy only when sensitive content must be removed.
- `wiki/`: reusable knowledge. Store concise, source-backed summaries, procedures, decisions, environment notes, pitfalls, and interface facts here.
- `schema/`: operating rules. Store agent instructions, write policies, naming conventions, privacy rules, and maintenance constraints here.

## Minimum Files

- `schema/AGENTS.md`: rules agents must read before working with the knowledge base.
- `wiki/index.md`: entrypoint and topic map.
- `wiki/overview.md`: project boundary and current state.
- `wiki/log.md`: append-only update log.

## Read Order

Read in this order before answering project-specific questions:

1. `schema/AGENTS.md`
2. `wiki/index.md`
3. `wiki/overview.md`
4. Relevant topic pages
5. `raw/` only when the answer needs source verification

## Write Rule

Write facts once. A durable fact should have one home page in `wiki/`, with links from index or related pages. Avoid spreading the same business rule or environment value across multiple pages.

## Knowledge Lifecycle

When a project needs Qoder-style automatic memory, cards, and repo wiki behavior, keep the same three top-level layers and express them as a lifecycle:

- Capture: source-backed observations under `raw/`.
- Distill: compact reusable cards under `wiki/cards/`.
- Stabilize: mature knowledge in canonical `wiki/` topic pages.
- Govern: read/write/promotion rules under `schema/`.
- Retire: stale or superseded knowledge marked in place and recorded in `wiki/log.md`.

See `references/knowledge-lifecycle.md` for promotion and confidence rules.

## Root Choices

Use a strict knowledge-base root when the directory exists only for knowledge management. In that root, allow only `raw/`, `schema/`, and `wiki/`.

When adding a knowledge base to a code repository, create it under a dedicated subdirectory such as `knowledge-base/`, then apply the same three-layer contract inside that subdirectory.
