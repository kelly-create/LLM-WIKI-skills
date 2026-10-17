#!/usr/bin/env python3
"""Validate the build-llm-wiki skill package without third-party dependencies."""

from __future__ import annotations

import argparse
import re
import json
from pathlib import Path
from llm_wiki.model import scan_secrets, configure_utf8


REQUIRED_PATHS = (
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/init_llm_wiki.py",
    "scripts/check_llm_wiki.py",
    "scripts/validate_skill.py",
    "scripts/wiki.py",
    "scripts/llm_wiki/model.py",
    "scripts/llm_wiki/storage.py",
    "scripts/llm_wiki/engine.py",
    "references/cli.md",
    "references/evaluation.md",
    "references/validation.md",
    "evals/scenarios.json",
    "references/architecture.md",
    "references/knowledge-lifecycle.md",
    "references/migration.md",
    "references/governance.md",
    "assets/templates/raw/memory-index.md",
    "assets/templates/schema/AGENTS.md",
    "assets/templates/wiki/card.md",
    "assets/templates/wiki/cards-index.md",
    "assets/templates/wiki/index.md",
    "assets/templates/wiki/overview.md",
    "assets/templates/wiki/log.md",
    "assets/templates/wiki/topic.md",
)

SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
RESOURCE_RE = re.compile(r"`((?:references|scripts|assets)/[A-Za-z0-9_./-]+)`")



def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def parse_frontmatter(skill_md: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        return {}, ["SKILL.md must start with YAML frontmatter delimiter ---"]

    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, ["SKILL.md frontmatter is missing closing --- delimiter"]

    metadata: dict[str, str] = {}
    for lineno, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            continue
        if ":" not in line:
            errors.append(f"invalid frontmatter line {lineno}: {line}")
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")

    extra = sorted(set(metadata) - {"name", "description"})
    if extra:
        errors.append("SKILL.md frontmatter has unsupported fields: " + ", ".join(extra))

    name = metadata.get("name", "")
    if not name:
        errors.append("SKILL.md frontmatter missing name")
    elif not SKILL_NAME_RE.match(name):
        errors.append("SKILL.md name must use lowercase letters, digits, and hyphens")

    description = metadata.get("description", "")
    if not description:
        errors.append("SKILL.md frontmatter missing description")
    elif "Use when" not in description:
        errors.append("SKILL.md description should include trigger guidance such as 'Use when ...'")

    return metadata, errors


def check_required_paths(root: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_PATHS:
        if not (root / name).exists():
            errors.append(f"missing required path: {name}")
    return errors


def check_openai_yaml(root: Path) -> list[str]:
    path = root / "agents" / "openai.yaml"
    if not path.exists():
        return ["missing agents/openai.yaml"]

    text = path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    for field in ("display_name", "short_description", "default_prompt"):
        if not re.search(rf"^\s*{re.escape(field)}\s*:", text, re.MULTILINE):
            errors.append(f"agents/openai.yaml missing interface.{field}")
    return errors


def check_resource_links(root: Path) -> list[str]:
    skill = root / "SKILL.md"
    text = skill.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []

    for target in sorted(set(RESOURCE_RE.findall(text))):
        normalized = target.rstrip("/")
        if normalized == "assets/templates":
            if not (root / normalized).is_dir():
                errors.append(f"referenced resource does not exist: {target}")
            continue
        if not (root / normalized).exists():
            errors.append(f"referenced resource does not exist: {target}")

    for path in [root / "README.md", skill, *(root / "references").glob("*.md")]:
        if not path.is_file():
            continue
        body = re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*$", "", path.read_text(encoding="utf-8"))
        for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", body):
            if target.startswith(("https://", "http://", "#")):
                continue
            candidate = (path.parent / target.split("#", 1)[0]).resolve()
            if not candidate.is_relative_to(root) or not candidate.exists():
                errors.append("broken documentation link in " + rel(path, root))

    return errors


def check_sensitive_content(root: Path) -> list[str]:
    return ["possible secret in " + item["path"] for item in scan_secrets(root)]


def check_python_compile(root: Path) -> list[str]:
    errors: list[str] = []
    for path in (root / "scripts").rglob("*.py"):
        try:
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
        except (SyntaxError, OSError) as exc:
            errors.append(f"python compile failed for {rel(path, root)}: {type(exc).__name__}")
    return errors


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser(description="Validate the build-llm-wiki skill package.")
    parser.add_argument("root", nargs="?", default=".", help="Skill repository root")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR: root does not exist: {root}")
        return 2

    errors: list[str] = []
    errors.extend(check_required_paths(root))
    if (root / "SKILL.md").exists():
        _, frontmatter_errors = parse_frontmatter(root / "SKILL.md")
        errors.extend(frontmatter_errors)
        errors.extend(check_resource_links(root))
    errors.extend(check_openai_yaml(root))
    errors.extend(check_sensitive_content(root))
    errors.extend(check_python_compile(root))

    if args.format == "json":
        print(json.dumps({"schema_version": 2, "command": "validate_skill", "status": "error" if errors else "ok", "diagnostics": errors}))
        return 1 if errors else 0
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1

    print(f"OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
