#!/usr/bin/env python3
"""Validate the build-llm-wiki skill package without third-party dependencies."""

from __future__ import annotations

import argparse
import py_compile
import re
import tempfile
from pathlib import Path


REQUIRED_PATHS = (
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/init_llm_wiki.py",
    "scripts/check_llm_wiki.py",
    "scripts/validate_skill.py",
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
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|cookie)\b\s*[:=]\s*"
        r"['\"]?[A-Za-z0-9_./+=@:-]{12,}"
    ),
    re.compile(r"(?i)\b(?:postgres|mysql|mongodb|redis)://[^ \n\r\t]+"),
)


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

    return errors


def check_sensitive_content(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".md", ".py", ".yaml", ".yml", ".json", ".txt", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret in {rel(path, root)}")
                break
    return errors


def check_python_compile(root: Path) -> list[str]:
    errors: list[str] = []
    scripts = ("scripts/init_llm_wiki.py", "scripts/check_llm_wiki.py", "scripts/validate_skill.py")
    with tempfile.TemporaryDirectory(prefix="build-llm-wiki-pycompile-") as tmp:
        out = Path(tmp)
        for script in scripts:
            path = root / script
            try:
                py_compile.compile(str(path), cfile=str(out / (path.stem + ".pyc")), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(f"python compile failed for {script}: {exc.msg}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the build-llm-wiki skill package.")
    parser.add_argument("root", nargs="?", default=".", help="Skill repository root")
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

    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1

    print(f"OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
