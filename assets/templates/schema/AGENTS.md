# Project Knowledge Base Rules

This directory is a three-layer LLM Wiki knowledge base.

## Layers

- `raw/`: source material and evidence.
- `wiki/`: structured knowledge derived from sources.
- `schema/`: rules that govern agent behavior and maintenance.

## Read Order

1. `schema/AGENTS.md`
2. `wiki/index.md`
3. `wiki/overview.md`
4. Relevant topic pages
5. `raw/` only when source verification is needed

## Write Rules

- Put source material in `raw/`.
- Put observations and unpromoted memory in `raw/memory/`.
- Put compact reusable findings in `wiki/cards/`.
- Put durable canonical summaries and reusable facts in `wiki/`.
- Put operating rules and constraints in `schema/`.
- Update `wiki/index.md` and `wiki/log.md` after meaningful changes.
- Prefer verified sources over stale wiki content.
- Record conflicts in `wiki/log.md`.
- Promote knowledge in order: raw source -> card -> canonical wiki page.
- Do not keep duplicate fact sources; link cards to canonical pages when promoted.

## Safety

Never write plaintext passwords, tokens, API keys, cookies, private keys, or connection strings.

## Project Boundary

- Project key: TODO
- Knowledge-base root: TODO
- Maintainer: TODO
