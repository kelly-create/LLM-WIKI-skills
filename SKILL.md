---
name: build-llm-wiki
description: Build, migrate, maintain, query, and validate a three-layer LLM Wiki knowledge lifecycle for agents. Use when an agent needs to create a project knowledge base from scratch, convert scattered notes or memory into raw/schema/wiki structure, record durable knowledge after work, read an existing LLM Wiki before answering, repair or validate a knowledge base, synthesize Qoder-style Repo Wiki / Knowledge Cards / Memory ideas into a governed capture-to-wiki lifecycle, or define safe multi-agent knowledge-management rules.
---

# Build LLM Wiki

## Overview

Use this skill to help an agent create and operate a compact three-layer LLM Wiki:

- `raw/`: source material and immutable evidence.
- `wiki/`: structured, reusable knowledge derived from sources.
- `schema/`: rules that govern how agents read, write, validate, and protect the knowledge base.

Keep the workflow simple. Do not turn the wiki into a second codebase or a dumping ground for transcripts.

Use a lifecycle, not three competing fact stores:

1. Capture observations and source material in `raw/`.
2. Distill small reusable findings into `wiki/cards/`.
3. Stabilize mature knowledge into canonical `wiki/` topic pages.
4. Govern read/write/promotion rules in `schema/`.
5. Retire stale knowledge with status labels and `wiki/log.md` entries.

## Operating Rule

Before changing anything, inspect the current directory and classify the situation:

1. New project with no knowledge base.
2. Existing project with scattered notes, memories, documents, logs, or exported chats.
3. Existing `raw/`, `schema/`, `wiki/` knowledge base.
4. Ordinary code or document repository where a knowledge base should be created under a dedicated path.
5. Read-only or restricted environment where only a proposed change set can be produced.

If the root already contains only `raw/`, `schema/`, and `wiki/`, treat that root as the knowledge-base root. In that case, do not create extra root-level files or directories.

If this skill is active because the user wants to build, initialize, or adopt an LLM Wiki, and the target has no knowledge base, initialize it automatically when the target path is clear and filesystem writes are allowed. Do not ask for confirmation just to create the standard starter structure. Ask only when the target path is ambiguous, the operation would overwrite existing files, the environment is read-only, or the current root has conflicting entries.

For new knowledge bases, use the deterministic initializer:

```bash
python scripts/init_llm_wiki.py <knowledge-base-root> --project-key <key> --purpose "<purpose>"
```

If the target is a normal code repository, default to a dedicated subdirectory such as `knowledge-base/` and initialize the three layers inside it.

## Core Capabilities

### 1. Identify and initialize

Determine whether to create, repair, or use a knowledge base. For a new strict knowledge-base root, create:

- `raw/`
- `schema/`
- `wiki/`
- `schema/AGENTS.md`
- `wiki/index.md`
- `wiki/overview.md`
- `wiki/log.md`
- `raw/memory/index.md`
- `wiki/cards/index.md`

Use the templates in `assets/templates/`. Adjust only project-specific names, paths, and boundaries.

When filesystem writes are allowed, run `scripts/init_llm_wiki.py` instead of hand-writing the starter files. The script never overwrites existing files unless `--force` is passed.

### 2. Collect and migrate

Move source material into `raw/` or record its location there. Source material includes old notes, exported memories, chats, Markdown files, docs, scripts, incident logs, command outputs, and design decisions.

Do not treat old memory as automatically true. Preserve provenance first, then extract durable knowledge.

### 3. Organize and write

Write only durable knowledge into `wiki/`: environment facts, interfaces, operating procedures, root causes, business rules, decisions, validation results, user preferences, and permission boundaries.

Write behavior rules and maintenance constraints into `schema/`. Update `wiki/index.md` and `wiki/log.md` whenever meaningful knowledge changes.

Filter out chat noise, unverified guesses, transient debugging steps, and repeated source content.

For Qoder-inspired workflows, do not merely map Repo Wiki, Knowledge Cards, and Memory into folders. Extract the useful behavior: automatic capture, compact reusable cards, searchable maturity signals, source-backed promotion, and stale-knowledge retirement. Read `references/knowledge-lifecycle.md` before designing or migrating that workflow.

### 4. Read and reuse

Before answering project-specific questions, read in this order:

1. `schema/AGENTS.md`
2. `wiki/index.md`
3. `wiki/overview.md`
4. Relevant topic pages
5. `raw/` sources only when facts need verification

Treat `wiki/` as organized knowledge, not the highest truth source. If `wiki/`, `raw/`, and live state conflict, prefer the verifiable source and record the conflict in `wiki/log.md`.

### 5. Validate and maintain

Run `scripts/check_llm_wiki.py <knowledge-base-root>` after initialization, migration, or repair. Fix structural errors before adding more knowledge.

Use status markers when knowledge changes over time: `active`, `deprecated`, `superseded`, or `needs-verification`.

### 6. Protect safety and collaboration boundaries

Never write plaintext passwords, API keys, tokens, cookies, private keys, or connection strings. Redact sensitive production data and personal information before writing summaries.

Do not create duplicate fact sources. Do not copy large raw material into `wiki/`. Do not rewrite project source code as part of wiki maintenance unless the user explicitly asks for code changes.

If the environment is read-only or permission-limited, output the exact proposed files or patch plan instead of claiming the wiki was updated.

## References

- For architecture and layer rules, read `references/architecture.md`.
- For the capture-to-card-to-wiki lifecycle, read `references/knowledge-lifecycle.md`.
- For migrating existing agent memory or old notes, read `references/migration.md`.
- For safety, conflicts, and lifecycle rules, read `references/governance.md`.
- For reusable starter files, copy from `assets/templates/`.
- For deterministic setup, run `scripts/init_llm_wiki.py`.
