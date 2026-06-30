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

## Knowledge Center View

When a project needs a Qoder-style knowledge center, keep the same three top-level layers and expose three views inside them:

- Repo Wiki: stable `wiki/` overview and topic pages.
- Knowledge Cards: compact `wiki/cards/` entries for atomic reusable knowledge.
- Memory: dated source-backed records under `raw/`, promoted only after verification.

See `references/knowledge-center.md` for promotion and maturity rules.

## Root Choices

Use a strict knowledge-base root when the directory exists only for knowledge management. In that root, allow only `raw/`, `schema/`, and `wiki/`.

When adding a knowledge base to a code repository, create it under a dedicated subdirectory such as `knowledge-base/`, then apply the same three-layer contract inside that subdirectory.
