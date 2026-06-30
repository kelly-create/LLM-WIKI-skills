# LLM Wiki Skills

Codex skill for building and maintaining a three-layer LLM Wiki knowledge base.

It helps agents start from zero, migrate scattered knowledge, and keep future work organized under a strict `raw/`, `schema/`, `wiki/` model.

## What It Does

- Initializes a new LLM Wiki from templates.
- Migrates existing notes, memories, exported chats, logs, and documents into traceable source material.
- Writes durable project knowledge into `wiki/`.
- Writes agent behavior rules and maintenance constraints into `schema/`.
- Reads an existing wiki before answering project-specific questions.
- Validates the structure and prevents duplicate or unsafe fact sources.

## Three Layers

```text
raw/     source material, imports, logs, snapshots, evidence
schema/  rules for how agents read, write, validate, and protect the wiki
wiki/    structured reusable knowledge derived from sources
```

If a project root contains only these three directories, the skill treats that root as the knowledge-base root and does not create extra root-level files.

## Install

From Codex, install the repository root as the skill:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo kelly-create/LLM-WIKI-skills \
  --path . \
  --name build-llm-wiki
```

Restart Codex after installation so the skill metadata is loaded.

## Quick Start

Ask Codex to use the skill:

```text
Use build-llm-wiki to initialize a knowledge base for this project.
```

For deterministic setup, the skill can run:

```bash
python scripts/init_llm_wiki.py <knowledge-base-root> --project-key <key> --purpose "<purpose>"
```

Then validate:

```bash
python scripts/check_llm_wiki.py <knowledge-base-root>
```

## What Runs Automatically

After installation, the skill can be selected automatically when the user asks to build, migrate, maintain, query, or validate an LLM Wiki.

When active, it automatically applies the read order and safety rules:

1. Read `schema/AGENTS.md`.
2. Read `wiki/index.md`.
3. Read `wiki/overview.md` and relevant topic pages when needed.
4. Check `raw/` only when facts need source verification.

It does not run as a background daemon. It does not create, migrate, overwrite, or delete files unless the user request or task context clearly calls for a write operation.

## How Future Agent Behavior Is Governed

The skill governs future work in two ways:

1. Skill triggering: when a user asks about LLM Wiki creation, migration, maintenance, reading, or validation, Codex can load `SKILL.md` and follow this workflow.
2. Project rules: after initialization, the target project has `schema/AGENTS.md`. Future agents working in that knowledge base should read it before answering or editing project knowledge.

For always-on background ingestion, scheduled sync, or cross-project monitoring, add a separate automation outside this skill. This repository intentionally stays focused on the reusable skill and its templates.

## Repository Layout

```text
SKILL.md
agents/openai.yaml
scripts/
  init_llm_wiki.py
  check_llm_wiki.py
references/
  architecture.md
  migration.md
  governance.md
assets/templates/
  schema/AGENTS.md
  wiki/index.md
  wiki/overview.md
  wiki/log.md
  wiki/topic.md
```

## Safety

Do not store plaintext passwords, API keys, tokens, cookies, private keys, connection strings, or unrelated personal data in the wiki.

Keep `raw/` as the evidence layer, `wiki/` as the derived knowledge layer, and `schema/` as the rule layer. Avoid copying large raw material into `wiki/`, and avoid creating multiple competing fact sources.
