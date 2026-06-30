# Knowledge Center Pattern

Use this pattern when adapting a Qoder-style knowledge center with Repo Wiki, Knowledge Cards, and Memory.

Do not create a fourth top-level layer. Keep the root contract as `raw/`, `schema/`, and `wiki/`.

## Mapping

| Knowledge center surface | LLM Wiki home | Purpose |
| --- | --- | --- |
| Repo Wiki | `wiki/overview.md`, topic pages, and `wiki/index.md` | Stable project knowledge for humans and agents |
| Knowledge Cards | `wiki/cards/*.md` | Small reusable facts, rules, pitfalls, commands, or decisions |
| Memory | `raw/memory/` or other dated `raw/` source folders | Chronological observations and unpromoted experience records |

## Repo Wiki

Use Repo Wiki pages for durable knowledge that has clear scope and enough evidence:

- project boundary and current state
- architecture, interfaces, commands, and deployment facts
- operating procedures
- long-lived business rules
- decisions and their source references

Repo Wiki pages should be concise and linked from `wiki/index.md`.

## Knowledge Cards

Use cards for atomic knowledge that agents should reuse quickly:

- one business rule
- one command pattern
- one environment fact
- one pitfall and fix
- one decision
- one user preference relevant to the project

Keep each card short. Use `assets/templates/wiki/card.md` for new cards.

Promote or merge a card into a topic page when it becomes part of a broader stable workflow. Keep only a link or deprecation note if the standalone card would become a duplicate fact source.

## Memory

Use memory records for observations that are useful but not yet stable enough for `wiki/`:

- session summaries
- imported agent memories
- incident notes
- repeated trial results
- unresolved hypotheses
- source excerpts that need later review

Store these under `raw/` with provenance and dates. Do not rely on memory as truth until it is checked against sources or live state.

## Promotion Rule

Promote knowledge in this order:

1. Capture source material in `raw/`.
2. Extract small reusable findings into `wiki/cards/` when they are useful but narrow.
3. Merge mature cards into stable topic pages when they become recurring project knowledge.
4. Update `wiki/index.md` and `wiki/log.md`.

Avoid copying the same fact into multiple cards and topic pages. Link instead.

## Search and Filtering

Cards should include enough metadata for filtering:

- `Status`: `active`, `deprecated`, `superseded`, or `needs-verification`
- `Maturity`: `low`, `medium`, or `high`
- `Source`: raw path, live check, or external source
- `Last verified`: date or `TODO`
- `Tags`: short comma-separated labels

Use maturity as a routing signal, not as proof. High-maturity cards still need source verification for high-risk answers.
