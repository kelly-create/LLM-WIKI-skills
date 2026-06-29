#!/usr/bin/env python3
"""Validate a three-layer LLM Wiki knowledge base."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_DIRS = ("raw", "schema", "wiki")
REQUIRED_FILES = (
    "schema/AGENTS.md",
    "wiki/index.md",
    "wiki/overview.md",
    "wiki/log.md",
)

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|cookie)\b\s*[:=]\s*"
        r"['\"]?[A-Za-z0-9_./+=@:-]{12,}"
    ),
    re.compile(r"(?i)\b(?:postgres|mysql|mongodb|redis)://[^ \n\r\t]+"),
)

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def check_structure(root: Path, allow_extra_root: bool) -> list[str]:
    errors: list[str] = []

    for name in REQUIRED_DIRS:
        if not (root / name).is_dir():
            errors.append(f"missing directory: {name}/")

    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            errors.append(f"missing file: {name}")

    if not allow_extra_root and root.exists():
        allowed = set(REQUIRED_DIRS)
        for item in root.iterdir():
            if item.name not in allowed:
                errors.append(f"extra root entry in strict mode: {item.name}")

    return errors


def check_wikilinks(root: Path) -> list[str]:
    errors: list[str] = []
    wiki = root / "wiki"
    if not wiki.is_dir():
        return errors

    pages = {p.stem for p in wiki.rglob("*.md")}
    for page in wiki.rglob("*.md"):
        text = page.read_text(encoding="utf-8", errors="replace")
        for target in WIKILINK_RE.findall(text):
            name = target.split("|", 1)[0].split("#", 1)[0].strip()
            if not name:
                continue
            if name.endswith(".md"):
                name = Path(name).stem
            if name not in pages:
                errors.append(f"broken wikilink in {rel(page, root)}: [[{target}]]")

    return errors


def check_sensitive_content(root: Path) -> list[str]:
    errors: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".env"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret in {rel(path, root)}")
                break

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a three-layer LLM Wiki root.")
    parser.add_argument("root", nargs="?", default=".", help="Knowledge-base root path")
    parser.add_argument(
        "--allow-extra-root",
        action="store_true",
        help="Allow files outside raw/schema/wiki when the wiki is embedded in a larger repo.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR: root does not exist: {root}")
        return 2

    errors: list[str] = []
    errors.extend(check_structure(root, args.allow_extra_root))
    errors.extend(check_wikilinks(root))
    errors.extend(check_sensitive_content(root))

    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1

    print(f"OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
