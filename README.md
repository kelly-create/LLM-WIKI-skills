# LLM Wiki Skills v2

给多种 agent 使用的本地项目知识库技能：**先查经验、操作前检查、失败后留证、修复后验证、下次复用**。

保留 raw（证据）、schema（规则）、wiki（知识）三层结构。Python 3.10+，运行时无第三方依赖；跨项目共享默认使用 ~/.llm-wiki/shared，项目事实保持隔离。

## 这次升级

- 统一 CLI：初始化、入口绑定、经验记录、验证、检索、预检、提升、健康检查、迁移和恢复。
- 中文/英文/错误码检索；返回匹配原因、来源、可信度和适用环境。
- 失败指纹去重；重复发生不会提高可信度。
- 只有当前有效、环境适用、操作匹配的已验证规则能够建议拦截。
- 来源指纹、复核日期、现场事实复核、冲突和替代链检查。
- 写入锁、并发修改检查、可恢复事务和显式迁移回滚。
- 敏感信息扫描覆盖 .env、日志和 JSONL；保留旧库只读兼容。
- Codex/Claude Code 项目入口使用托管区块，保留已有指令。

技能依赖 agent 实际调用；CLI 不会自行拦截所有工具。宿主需要消费 preflight 的返回值才能强制执行。知识与证据不构成额外操作权限。

## 安装

Codex：
```sh
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo kelly-create/LLM-WIKI-skills --path . --name build-llm-wiki
```

Claude Code：将仓库内容复制到 ~/.claude/skills/build-llm-wiki/，通过 /build-llm-wiki 使用。
其他支持 Agent Skills 或本地 Python 脚本的 agent 可使用同一 CLI。
已安装的旧版本不会因仓库更新而自动升级；安装应选择经过验证的提交或发布版本。
当前开发分支的功能在合并/发布前不会出现在默认分支安装中。

## 快速开始

在项目目录执行；将 `<skill>` 替换为技能安装目录的绝对路径。
```sh
python "<skill>/scripts/wiki.py" init ./knowledge-base --project-root . --project-key demo --format json
python "<skill>/scripts/wiki.py" bind ./knowledge-base --agent all --format json
python "<skill>/scripts/wiki.py" preflight ./knowledge-base --query "具体报错和症状" --context context.json --format json
python "<skill>/scripts/wiki.py" check ./knowledge-base --format json
```

context.json 示例：
```json
{"operation":"deploy","environment":{"os":"linux","arch":"arm64"}}
```

完整输入示例和退出码见 [CLI 文档](references/cli.md)。
preflight 同时返回匹配经验和检查结果；尚未确定操作时使用 search 检索。
记录经验使用 record；完成真实修复验证后使用 resolve；promotion 保留证据链。
无 Python 时可人工读取文件，但不能宣称自动校验、事务写入或预检已经执行。

## 旧库升级

旧初始化和校验命令仍可用。旧卡片不会被自动重写或自动视为可信结论。
```sh
python scripts/wiki.py migrate /path/to/knowledge-base --format json
python scripts/wiki.py migrate /path/to/knowledge-base --apply --format json
```
先预览，再显式应用。无法可靠转换的内容保留原文。备份和回滚见 [迁移说明](references/migration.md)。
--force 仍接受，但不再覆盖积累的知识和日志。普通目录使用独立知识库子目录。

## 开发与验证

```sh
python scripts/validate_skill.py .
python -m unittest discover -s tests -v
python scripts/evaluate.py --mode offline --output .eval-runs/offline.json
python scripts/package_skill.py
```

CI 矩阵配置为 Windows/Linux、Python 3.10/3.15。打包脚本会生成 dist/build-llm-wiki-2.0.0.zip，并解压校验入口。
真实 agent 回放单独触发，不在日常 CI 中调用模型。
[评测说明](references/evaluation.md) 区分离线检索结果、宿主接入检查与真实模型对照指标。
当前状态和复现命令记录在 [验证记录](references/validation.md)，未测出的性能目标不会标为达成。
本次 Codex 跨会话验收已通过，优化后的 120 次有效模型对照已完成：两版修复成功率和经验命中前三均为 60/60。
新版工具调用中位数从 10 次降到 9 次，减少 10%，未达到 20% 目标。实际动作测量完整，两版重复错误均为 0，无法证明减少 50%。
75 项回归已在 Windows/Linux 验证；功能检查通过，发布效果门槛仍未全部通过。当前作为 v2 测试版提供。
Claude 已按用户要求移出本次必测范围，平台支持仍标为未验证。

## 文件结构

- SKILL.md：简短技能入口，按任务加载参考文档。
- scripts/wiki.py：统一命令；scripts/llm_wiki/：契约、事务和生命周期逻辑。
- scripts/init_llm_wiki.py、check_llm_wiki.py、validate_skill.py：兼容入口和包自检。
- references/：架构、命令、生命周期、治理、迁移与评测说明。
- assets/templates/：可复用规则和知识模板。
- tests/、evals/：离线回归和可重复排障场景。

## English

Portable, local-first experience management for agents. Search before substantial work,
preflight known prerequisites, capture redacted failures, and verify repairs before reuse.
Markdown remains human-readable; v2 metadata is JSON in a bounded frontmatter block.
Runtime dependencies: Python 3.10+ standard library. Shared experiences preserve their
tested scope; legacy knowledge is readable but requires re-verification.
See the English [CLI reference](references/cli.md) and [architecture](references/architecture.md).
