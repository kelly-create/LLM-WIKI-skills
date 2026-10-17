#!/usr/bin/env python3
"""Build a deterministic, validated skill archive without personal/runtime files."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from llm_wiki import VERSION
from llm_wiki.model import digest, configure_utf8

ROOT = Path(__file__).resolve().parents[1]
NAME = "build-llm-wiki"


def build(output: Path):
    validation = subprocess.run([sys.executable, str(ROOT / "scripts/validate_skill.py"), str(ROOT), "--format", "json"],
                                capture_output=True, text=True, encoding="utf-8")
    if validation.returncode:
        raise ValueError("package validation failed; run validate_skill.py for diagnostics")
    paths = [ROOT / "SKILL.md", ROOT / "README.md"]
    for directory in ("agents", "assets", "references", "scripts", "tests", "evals"):
        paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix != ".pyc")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            if not path.resolve().is_relative_to(ROOT):
                raise ValueError("package file escapes repository")
            info = zipfile.ZipInfo(NAME + "/" + path.relative_to(ROOT).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    # Validate exactly the bytes a recipient would extract, including entrypoint imports.
    with tempfile.TemporaryDirectory(prefix="package-check-", dir=output.parent) as name:
        with zipfile.ZipFile(output) as archive:
            archive.extractall(name)
        root = Path(name) / NAME
        for arguments in ([str(root / "scripts/validate_skill.py"), str(root), "--format", "json"],
                          [str(root / "scripts/wiki.py"), "--version"]):
            result = subprocess.run([sys.executable, *arguments], capture_output=True, text=True, encoding="utf-8")
            if result.returncode:
                raise ValueError("extracted package validation failed")
    return {"schema_version": 2, "status": "ok", "version": VERSION, "output": str(output),
            "sha256": digest(output.read_bytes()), "files": len(paths), "extracted_validation": "passed"}


def main():
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / (NAME + "-" + VERSION + ".zip"))
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output.resolve()), ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"schema_version": 2, "status": "error", "diagnostics": [str(exc) if isinstance(exc, ValueError) else "filesystem unavailable"]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
