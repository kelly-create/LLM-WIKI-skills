#!/usr/bin/env python3
"""Initialize a three-layer LLM Wiki knowledge base."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path


TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "assets" / "templates"
FILES = (
    ("schema/AGENTS.md", "schema/AGENTS.md"),
    ("wiki/index.md", "wiki/index.md"),
    ("wiki/overview.md", "wiki/overview.md"),
    ("wiki/log.md", "wiki/log.md"),
    ("wiki/cards-index.md", "wiki/cards/index.md"),
)


def render_template(text: str, values: dict[str, str]) -> str:
    replacements = {
        "Project key: TODO": f"Project key: {values['project_key']}",
        "Purpose: TODO": f"Purpose: {values['purpose']}",
        "Knowledge-base root: TODO": f"Knowledge-base root: {values['root']}",
        "Maintainer: TODO": f"Maintainer: {values['maintainer']}",
        "Last reviewed: TODO": f"Last reviewed: {values['today']}",
        "Open verification items: TODO": "Open verification items: none recorded",
        "## YYYY-MM-DD | init": f"## {values['today']} | init",
        "- Source: TODO": "- Source: initialized by build-llm-wiki.",
        "- Notes: TODO": f"- Notes: {values['purpose']}",
        "- TODO: add first dated update.": f"- {values['today']}: initialized three-layer LLM Wiki.",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def ensure_root(root: Path, strict_root: bool) -> list[str]:
    root.mkdir(parents=True, exist_ok=True)
    if not strict_root:
        return []

    allowed = {"raw", "schema", "wiki"}
    extras = [item.name for item in root.iterdir() if item.name not in allowed]
    return extras


def write_file(path: Path, content: str, force: bool) -> str:
    existed = path.exists()
    if existed and not force:
        return "skipped"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return "written" if existed else "created"


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a three-layer LLM Wiki.")
    parser.add_argument("root", help="Knowledge-base root to initialize")
    parser.add_argument("--project-key", default="project", help="Short project key")
    parser.add_argument("--purpose", default="Project knowledge base", help="Knowledge-base purpose")
    parser.add_argument("--maintainer", default="agents", help="Maintainer label")
    parser.add_argument(
        "--strict-root",
        action="store_true",
        help="Fail if root contains entries other than raw, schema, and wiki",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing starter files")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    extras = ensure_root(root, args.strict_root)
    if extras:
        print("ERROR: strict root contains extra entries: " + ", ".join(sorted(extras)))
        return 1

    values = {
        "project_key": args.project_key,
        "purpose": args.purpose,
        "maintainer": args.maintainer,
        "root": str(root),
        "today": date.today().isoformat(),
    }

    for name in ("raw", "schema", "wiki"):
        (root / name).mkdir(parents=True, exist_ok=True)

    results: list[str] = []
    for source, target in FILES:
        template = (TEMPLATE_ROOT / source).read_text(encoding="utf-8")
        status = write_file(root / target, render_template(template, values), args.force)
        results.append(f"{status}: {target}")

    for line in results:
        print(line)
    print(f"OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
