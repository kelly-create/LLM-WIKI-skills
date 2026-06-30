# Knowledge Lifecycle

Use this protocol to combine the best parts of Qoder-style knowledge centers and the three-layer LLM Wiki.

The goal is not to clone Repo Wiki, Knowledge Cards, and Memory as separate fact stores. The goal is to move knowledge through a governed lifecycle so agents can capture experience quickly, reuse it safely, and retire it when stale.

## Extracted Strengths

Qoder-style knowledge centers are strong at:

- automatic memory capture during work
- compact knowledge cards for reusable snippets
- visible search, filtering, and maturity signals
- a Repo Wiki surface that is easy for humans to browse

The three-layer LLM Wiki is strong at:

- separating sources, rules, and derived knowledge
- preserving provenance and evidence
- avoiding duplicate fact sources
- staying portable across agents and tools
- enforcing safety and collaboration boundaries

## Synthesized Lifecycle

| Stage | Home | Purpose | Exit Rule |
| --- | --- | --- | --- |
| Capture | `raw/` and `raw/memory/` | Preserve observations, imports, logs, and source evidence | A reusable finding is identified |
| Distill | `wiki/cards/` | Store one compact claim, rule, pitfall, command, or decision | The finding is verified or repeatedly reused |
| Stabilize | `wiki/` topic pages | Maintain canonical project knowledge | The fact becomes durable project context |
| Govern | `schema/` | Define read, write, promotion, safety, and collaboration rules | Rules are reflected in agent behavior |
| Retire | status labels and `wiki/log.md` | Mark stale, superseded, or deprecated knowledge | Readers can find the replacement or reason |

## Promotion Rules

Promote knowledge only in one direction:

1. Capture source material in `raw/`.
2. Distill reusable findings into `wiki/cards/`.
3. Stabilize mature findings into canonical topic pages.
4. Record meaningful changes in `wiki/log.md`.
5. Mark old cards or pages as `superseded` or `deprecated` instead of duplicating facts.

Skip the card stage only for clearly broad, verified project knowledge that naturally belongs in a topic page.

## Card Contract

Every card should be atomic and include:

- `Status`: `active`, `needs-verification`, `superseded`, or `deprecated`
- `Confidence`: `observed`, `inferred`, or `verified`
- `Scope`: where the claim applies
- `Source`: raw path, live check, or external source
- `Last verified`: date or `TODO`
- `Tags`: short labels for retrieval

Confidence meanings:

- `observed`: captured from a session, log, screenshot, or note, but not generalized.
- `inferred`: reasoned from available evidence, but not directly verified.
- `verified`: checked against a direct source, live state, test, or repeated reliable use.

High-risk answers should not rely on `observed` or `inferred` cards without source verification.

## Canonicalization

When a card becomes part of stable project knowledge:

1. Move or summarize the fact into the relevant topic page.
2. Link the card to the canonical page.
3. Mark the card `superseded` if keeping it would create a duplicate fact source.
4. Update `wiki/index.md` when a new topic page is created.
5. Update `wiki/log.md` with the source and reason.

## Agent Workflow

When working in a project with this skill:

1. Read `schema/AGENTS.md`, then `wiki/index.md`.
2. Use topic pages for stable facts.
3. Use cards for compact reusable findings.
4. Use `raw/` when a claim needs source verification.
5. After meaningful work, capture new evidence in `raw/`, distill reusable findings into cards, and promote only verified durable facts.

## Invariants

- Do not keep private parallel memory when a shared wiki exists.
- Do not write the same durable fact into multiple places.
- Do not promote secrets or unnecessary personal data.
- Do not treat generated memory as truth without provenance.
- Do not make the lifecycle a blocker for simple tasks; capture only what will help future agents.
