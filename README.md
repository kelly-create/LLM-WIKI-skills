# LLM Wiki Skills

## 中文

### 项目功能

这是一个给 Codex/Agent 使用的知识库 skill，用来从 0 构建、迁移、维护和读取项目知识库。

它保持三层架构，同时引入知识生命周期：

- 帮项目自动初始化 `raw/`、`schema/`、`wiki/`。
- 把聊天、日志、截图、旧记忆、导入材料先保存为可追溯来源。
- 把可复用的小经验提炼成知识卡片。
- 把成熟、验证过的内容固化成项目 Wiki。
- 用规则层约束后续 agent 的读写、提升、废弃和安全边界。
- 校验结构、链接、敏感信息和知识卡片元数据。

### 三层架构

```text
raw/      来源层：记忆、日志、导入资料、操作记录、证据
schema/   规则层：agent 行为规则、读写规则、提升规则、安全边界
wiki/     知识层：知识卡片、主题页、概览、索引、稳定结论
```

### 知识生命周期

| 阶段 | 位置 | 作用 |
| --- | --- | --- |
| Capture 捕获 | `raw/memory/`、其他 `raw/` 目录 | 保存原始观察和证据 |
| Distill 提炼 | `wiki/cards/*.md` | 形成小而可复用的知识卡片 |
| Stabilize 固化 | `wiki/overview.md`、主题页、`wiki/index.md` | 维护稳定项目知识 |
| Govern 治理 | `schema/AGENTS.md`、规则文档 | 约束读写、提升、安全和协作 |
| Retire 淘汰 | 状态标记、`wiki/log.md` | 标记过期、替代或废弃知识 |

### 安装

在 Codex 中从 GitHub 安装仓库根目录：

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo kelly-create/LLM-WIKI-skills \
  --path . \
  --name build-llm-wiki
```

安装后重启 Codex，让 skill 元数据生效。

### 快速用法

对 Codex 说：

```text
Use build-llm-wiki to initialize a knowledge base for this project.
```

也可以直接运行初始化脚本：

```bash
python scripts/init_llm_wiki.py <knowledge-base-root> --project-key <key> --purpose "<purpose>"
```

初始化后校验：

```bash
python scripts/check_llm_wiki.py <knowledge-base-root>
```

### 自动行为

- 当用户要求构建、迁移、维护、查询或校验 LLM Wiki 时，Codex 可以自动触发这个 skill。
- 目标路径明确且可写时，会自动创建标准三层结构和 starter files。
- 它不会作为后台守护进程持续运行。
- 路径不明确、会覆盖文件、环境只读或根目录冲突时，会先询问。

### 仓库结构

```text
SKILL.md
agents/openai.yaml
scripts/
  init_llm_wiki.py
  check_llm_wiki.py
references/
  architecture.md
  knowledge-lifecycle.md
  migration.md
  governance.md
assets/templates/
  raw/memory-index.md
  schema/AGENTS.md
  wiki/card.md
  wiki/cards-index.md
  wiki/index.md
  wiki/overview.md
  wiki/log.md
  wiki/topic.md
```

### 安全规则

不要把明文密码、API key、token、cookie、私钥、连接串或无关个人信息写入知识库。

`raw/` 是证据层，`wiki/` 是知识层，`schema/` 是规则层。稳定事实只保留一个权威位置，其他地方用链接引用，避免制造多个事实源。

## English (Optional)

### What This Project Does

This repository provides a Codex skill for building and maintaining a three-layer LLM Wiki knowledge lifecycle.

It helps agents initialize a knowledge base, preserve source evidence, distill reusable knowledge cards, stabilize verified knowledge into wiki pages, and enforce governance rules for future agents.

### Architecture

```text
raw/      sources, memory, logs, imports, evidence
schema/   agent rules, write rules, promotion rules, safety boundaries
wiki/     cards, topic pages, overview, index, stable knowledge
```

### Lifecycle

| Stage | Location | Purpose |
| --- | --- | --- |
| Capture | `raw/memory/` and `raw/` | preserve observations and evidence |
| Distill | `wiki/cards/*.md` | create compact reusable findings |
| Stabilize | `wiki/` topic pages | maintain canonical project knowledge |
| Govern | `schema/` | define agent behavior and safety rules |
| Retire | status labels and `wiki/log.md` | mark stale or replaced knowledge |

### Install

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo kelly-create/LLM-WIKI-skills \
  --path . \
  --name build-llm-wiki
```

Restart Codex after installation.

### Quick Start

```text
Use build-llm-wiki to initialize a knowledge base for this project.
```

Validate after initialization:

```bash
python scripts/check_llm_wiki.py <knowledge-base-root>
```
