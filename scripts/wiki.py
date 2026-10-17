#!/usr/bin/env python3
"""Public CLI. All errors are redacted; JSON is supported by every command."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm_wiki import VERSION
from llm_wiki.engine import Wiki
from llm_wiki.model import WikiError, json_text, load_json, redact, configure_utf8


def parser():
    cli = argparse.ArgumentParser(description="LLM Wiki v2: evidence-backed experience and preflight")
    cli.add_argument("--version", action="version", version=VERSION)
    subs = cli.add_subparsers(dest="command", required=True)
    for command in ("init", "bind", "search", "preflight", "record", "resolve", "promote", "check", "doctor", "reindex", "migrate", "recover"):
        sub = subs.add_parser(command)
        sub.add_argument("root", nargs="?", default=".")
        sub.add_argument("--format", choices=("json", "text"), default="text")
        if command in {"init", "check", "doctor"}:
            sub.add_argument("--allow-extra-root", action="store_true")
        if command == "init":
            sub.add_argument("--project-key", default="project")
            sub.add_argument("--purpose", default="Project knowledge base")
            sub.add_argument("--maintainer", default="agents")
            sub.add_argument("--project-root")
            sub.add_argument("--shared-root")
            sub.add_argument("--shared", action="store_true")
            sub.add_argument("--strict-root", action="store_true", help="Compatibility alias; strict is the default")
            sub.add_argument("--force", action="store_true", help="Compatibility flag; existing knowledge is preserved")
        if command == "bind":
            sub.add_argument("--agent", choices=("codex", "claude", "generic", "all"), default="all")
            sub.add_argument("--project-root")
        if command in {"record", "resolve", "promote"}:
            sub.add_argument("--input", default="-", help="JSON file, or - for stdin")
            sub.add_argument("--operation-id")
        if command in {"resolve", "promote"}:
            sub.add_argument("--id", required=command == "promote")
        if command == "promote":
            sub.add_argument("--target", choices=("topic", "shared"), default="topic")
        if command in {"search", "preflight"}:
            sub.add_argument("--query", required=True)
            sub.add_argument("--context", help="JSON file, or - for stdin")
        if command == "search":
            sub.add_argument("--limit", type=int, default=5)
            sub.add_argument("--budget", type=int, default=6000)
            sub.add_argument("--no-shared", action="store_true")
        if command == "migrate":
            sub.add_argument("--apply", action="store_true")
        if command == "recover":
            sub.add_argument("--operation-id")
            sub.add_argument("--rollback", action="store_true")
            sub.add_argument("--break-lock", action="store_true")
    return cli


def input_json(name):
    text = sys.stdin.read() if name == "-" else Path(name).read_text(encoding="utf-8")
    value = load_json(text)
    if not isinstance(value, dict):
        raise WikiError("input must be a JSON object")
    return value


def main(argv=None):
    configure_utf8()
    args = parser().parse_args(argv)
    code = 0
    try:
        wiki = Wiki(args.root)
        cmd = args.command
        if cmd == "init":
            result = wiki.init(args.project_key, args.purpose, args.maintainer, args.project_root,
                               args.shared_root, args.shared, args.allow_extra_root and not args.strict_root, args.force)
        elif cmd == "bind":
            result = wiki.bind(args.agent, args.project_root)
        elif cmd in {"check", "doctor"}:
            result = wiki.check(args.allow_extra_root, cmd == "doctor")
            code = 0 if result["healthy"] else 1
        elif cmd in {"search", "preflight"}:
            context = input_json(args.context) if args.context else {}
            if cmd == "search":
                result = wiki.search(args.query, context, args.limit, args.budget, not args.no_shared)
            else:
                result = wiki.preflight(args.query, context)
                code = 3 if result["decision"] == "block" else 0
        elif cmd == "record":
            result = wiki.record(input_json(args.input), args.operation_id)
        elif cmd == "resolve":
            result = wiki.resolve(args.id, input_json(args.input), args.operation_id)
        elif cmd == "promote":
            payload = input_json(args.input) if args.target == "shared" or args.input != "-" else {}
            result = wiki.promote(args.id, args.target, payload, args.operation_id)
        elif cmd == "reindex":
            result = wiki.reindex()
        elif cmd == "migrate":
            result = wiki.migrate(args.apply)
        else:
            result = wiki.store.recover(args.operation_id, args.rollback, args.break_lock)
        result = {"schema_version": 2, "command": cmd, "status": "blocked" if code == 3 else "error" if code else "ok",
                  "diagnostics": [], "knowledge_ids": ([result["id"]] if "id" in result else [h["id"] for h in result.get("hits", [])]),
                  "evidence": [], **result}
    except (WikiError, OSError, UnicodeError) as exc:
        message = str(exc) if isinstance(exc, WikiError) else "filesystem unavailable or invalid text encoding"
        result = {"schema_version": 2, "command": args.command, "status": "error", "knowledge_ids": [], "evidence": [],
                  "diagnostics": [{"code": "operation_failed", "message": redact(message), "severity": "error"}]}
        code = 2
    output = json_text(result)
    if args.format == "json":
        print(output, end="")
    else:
        print(f"{result['status'].upper()}: {args.command}")
        print(output, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
