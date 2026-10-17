"""Document contracts, bounded parsing, provenance and content safety."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit


class WikiError(ValueError):
    """A safe diagnostic: never include input values or secret-bearing content."""


def configure_utf8():
    """Keep the CLI wire format independent of Windows console and pipe codepages."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


STATUSES = {"active", "needs-verification", "superseded", "deprecated"}
CONFIDENCES = {"observed", "inferred", "verified"}
KINDS = {"lesson", "fact", "procedure", "decision", "topic", "overview"}
INFRA = {".git", ".gitignore", ".gitattributes", ".gitmodules", "AGENTS.md", "CLAUDE.md", "README.md"}
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)")
ASSIGNMENT = re.compile(r'''(?im)(["']?\b[\w-]*(?:api[_-]?key|secret|token|password|passwd|cookie)[\w-]*\b["']?[ \t]*[:=][ \t]*["']?)([^\s"',;}{]{8,})''')
TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b")
CONNECTION = re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s\"'<>]+")
AUTH = re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|basic)\s+)[^\s\"']+")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def today() -> str:
    return date.today().isoformat()


def digest(content: str | bytes) -> str:
    return hashlib.sha256(content.encode("utf-8") if isinstance(content, str) else content).hexdigest()


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WikiError("duplicate JSON field")
        result[key] = value
    return result


def load_json(text: str):
    try:
        return json.loads(text, object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(WikiError("non-finite JSON number")))
    except json.JSONDecodeError as exc:
        raise WikiError("invalid JSON") from exc


def redact(text: str) -> str:
    text = PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", text)
    text = CONNECTION.sub("[REDACTED CONNECTION]", text)
    text = AUTH.sub(lambda m: m[1] + "[REDACTED]", text)
    text = TOKEN.sub("[REDACTED TOKEN]", text)
    def assignment(match):
        placeholder = match[2].upper().startswith(("[REDACTED", "<", "${"))
        # Exclude these source-code constructors, not arbitrary parenthesized passwords.
        constructor = not match[1].rstrip().endswith(("'", '"')) and match[2].startswith(("re.compile(", "uuid.uuid4("))
        return match[0] if placeholder or constructor else match[1] + "[REDACTED]"
    return ASSIGNMENT.sub(assignment, text)


def has_secret(text: str) -> bool:
    return redact(text) != text


def require_safe(text: str):
    if has_secret(text):
        raise WikiError("possible sensitive content; redact before writing")


def safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise WikiError("invalid relative path")
    # Treat Windows drive paths as absolute even when running on Linux.
    if Path(relative).is_absolute() or re.match(r"^[A-Za-z]:", relative) or relative.startswith(("\\", "/")):
        raise WikiError("absolute reference is not allowed")
    target = (root / relative.replace("\\", "/")).resolve()
    if not target.is_relative_to(root.resolve()):
        raise WikiError("path escapes permitted root")
    return target


def valid_date(value) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def serialize(metadata: dict, body: str) -> str:
    return "---\n" + json_text(metadata) + "---\n\n" + body.strip() + "\n"


def parse_document(text: str, relative: str = "") -> dict:
    errors = []
    if text.startswith("---\n") or text.startswith("---\r\n"):
        lines = text.splitlines()
        try:
            end = lines.index("---", 1)
            meta = load_json("\n".join(lines[1:end]))
            if not isinstance(meta, dict):
                raise WikiError("metadata must be an object")
        except (ValueError, WikiError):
            return {"metadata": {}, "body": text, "legacy": False, "errors": ["invalid or duplicate metadata"], "path": relative}
        return {"metadata": meta, "body": "\n".join(lines[end + 1:]).strip(), "legacy": False, "errors": [], "path": relative}
    # Only the initial list after the title is metadata, never later prose/code.
    meta = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].startswith("# "):
        i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines):
        match = re.fullmatch(r"-\s*([^:]+):\s*(.*)", lines[i])
        if not match:
            break
        key, value = match[1].strip(), match[2].strip()
        if key in meta:
            errors.append("duplicate legacy metadata")
        meta[key] = value
        i += 1
    return {"metadata": meta, "body": text, "legacy": True, "errors": errors, "path": relative}


def source_errors(source, root: Path, project_root: Path) -> list[str]:
    if not isinstance(source, dict):
        return ["source must be an object"]
    kind = source.get("type")
    if not isinstance(kind, str):
        return ["invalid source type"]
    if kind in {"file", "project_file"}:
        try:
            path = safe_path(root if kind == "file" else project_root, source.get("path"))
            if not path.is_file():
                return ["source file missing"]
            expected = source.get("sha256")
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                return ["source fingerprint missing or invalid"]
            if digest(path.read_bytes()) != expected:
                return ["source changed; reverify"]
        except (WikiError, OSError):
            return ["source path invalid or inaccessible"]
    elif kind == "url":
        url = source.get("url", "")
        if not isinstance(url, str):
            return ["invalid source URL"]
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                return ["invalid source URL"]
        except (TypeError, ValueError):
            return ["invalid source URL"]
        if not valid_date(source.get("checked_at")) or source["checked_at"] > today():
            return ["external source requires checked_at date"]
    else:
        return ["unsupported source type"]
    return []


def metadata_errors(meta: dict, root: Path, project_root: Path, check_sources: bool = True) -> list[str]:
    errors = []
    for field in ("verified_at", "review_after", "superseded_by"):
        if field not in meta:
            errors.append(f"missing {field}")
    if meta.get("schema_version") != 2:
        errors.append("unsupported schema_version")
    for key in ("id", "project_id", "title"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            errors.append(f"missing or empty {key}")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(meta.get("id", ""))):
        errors.append("invalid id")
    for key, allowed in (("status", STATUSES), ("confidence", CONFIDENCES), ("kind", KINDS)):
        if not isinstance(meta.get(key), str) or meta[key] not in allowed:
            errors.append(f"invalid {key}")
    if not isinstance(meta.get("scope"), dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in meta.get("scope", {}).items()):
        errors.append("scope must map environment keys to nonempty strings")
    for field in ("tags", "related", "conflicts"):
        if not isinstance(meta.get(field), list) or any(not isinstance(x, str) or not x for x in meta.get(field, [])):
            errors.append(f"{field} must be a string list")
    sources = meta.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources required")
    elif check_sources:
        for source in sources:
            errors.extend(source_errors(source, root, project_root))
    for field in ("verified_at", "review_after"):
        if meta.get(field) is not None and not valid_date(meta[field]):
            errors.append(f"invalid {field}")
    if valid_date(meta.get("verified_at")) and meta["verified_at"] > today():
        errors.append("verification date cannot be in the future")
    if meta.get("confidence") == "verified":
        if not valid_date(meta.get("verified_at")) or meta.get("verified_at", "") > today():
            errors.append("verified knowledge requires a non-future verification date")
        verification = meta.get("verification")
        if not isinstance(verification, dict) or verification.get("outcome") != "passed" or not isinstance(verification.get("method"), str) or not verification["method"].strip():
            errors.append("verified knowledge requires successful verification evidence")
        elif verification.get("scope") != meta.get("scope"):
            errors.append("verification scope must match knowledge scope")
    if meta.get("status") == "superseded" and not isinstance(meta.get("superseded_by"), str):
        errors.append("superseded knowledge requires replacement id")
    if meta.get("superseded_by") is not None and (not isinstance(meta["superseded_by"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", meta["superseded_by"])):
        errors.append("invalid replacement id")
    if "operation" in meta and (not isinstance(meta["operation"], str) or not meta["operation"].strip()):
        errors.append("operation must be a nonempty string")
    if "volatile" in meta and not isinstance(meta["volatile"], bool):
        errors.append("volatile must be boolean")
    if "occurrences" in meta and (type(meta["occurrences"]) is not int or meta["occurrences"] < 1):
        errors.append("occurrences must be a positive integer")
    if "history_sources" in meta and not isinstance(meta["history_sources"], list):
        errors.append("history_sources must be a list")
    for field in ("fingerprint", "error_signature"):
        if meta.get(field) is not None and not isinstance(meta[field], str):
            errors.append(f"invalid {field}")
    if "occurrences" in meta and (type(meta["occurrences"]) is not int or meta["occurrences"] < 1):
        errors.append("occurrences must be a positive integer")
    if "history_sources" in meta and not isinstance(meta["history_sources"], list):
        errors.append("history_sources must be a list")
    for field in ("fingerprint", "error_signature"):
        if meta.get(field) is not None and not isinstance(meta[field], str):
            errors.append(f"invalid {field}")
    rules = meta.get("rules", [])
    if not isinstance(rules, list):
        errors.append("rules must be a list")
    else:
        for rule in rules:
            if not isinstance(rule, dict) or not isinstance(rule.get("condition"), str) or rule["condition"] not in {"file_exists", "environment", "source_fingerprint", "evidence_present"}:
                errors.append("unsupported declarative condition")
                continue
            if rule.get("on_failure", "warn") not in ("warn", "block") or not isinstance(rule.get("message", ""), str):
                errors.append("invalid rule action or message")
            condition = rule["condition"]
            if condition in {"file_exists", "source_fingerprint"}:
                try:
                    if rule.get("base", "project") not in ("project", "knowledge"):
                        raise WikiError("invalid base")
                    safe_path(project_root if rule.get("base", "project") == "project" else root, rule.get("path"))
                except WikiError:
                    errors.append("invalid rule path")
            if condition == "file_exists" and not isinstance(rule.get("expect", True), bool):
                errors.append("file_exists expect must be boolean")
            if condition == "environment" and (not isinstance(rule.get("key"), str) or not isinstance(rule.get("equals"), str)):
                errors.append("environment condition requires key and equals")
            if condition == "source_fingerprint" and not re.fullmatch(r"[0-9a-f]{64}", str(rule.get("sha256", ""))):
                errors.append("source_fingerprint requires sha256")
            if condition == "evidence_present" and not isinstance(rule.get("id"), str):
                errors.append("evidence_present requires id")
    return errors


def legacy_errors(doc: dict, root: Path) -> list[str]:
    meta = doc["metadata"]
    errors = list(doc["errors"])
    required = ["Status", "Source", "Last verified"]
    if doc["path"].startswith("wiki/cards/"):
        required += ["Confidence", "Scope", "Tags"]
    for key in required:
        if not meta.get(key) or meta[key].upper() == "TODO":
            errors.append(f"legacy missing or unresolved {key}")
    if meta.get("Status") not in STATUSES:
        errors.append("invalid legacy Status")
    if "Confidence" in meta and meta["Confidence"] not in CONFIDENCES:
        errors.append("invalid legacy Confidence")
    if meta.get("Last verified") and not valid_date(meta["Last verified"]):
        errors.append("invalid legacy verification date")
    elif meta.get("Last verified") and meta["Last verified"] > today():
        errors.append("legacy verification date cannot be in the future")
    source = meta.get("Source", "").strip("`")
    if source.startswith("raw/"):
        try:
            if not safe_path(root, source).is_file():
                errors.append("legacy source file missing")
        except WikiError:
            errors.append("legacy source outside root")
    elif source and not source.startswith(("https://", "http://")):
        errors.append("legacy source cannot be mechanically verified")
    if meta.get("Status") == "superseded" and not meta.get("Canonical page"):
        errors.append("legacy replacement missing")
    return errors


def content_files(root: Path):
    for path in sorted(root.rglob("*")):
        if any(part in {".git", ".state", ".eval-runs", ".test-tmp", "__pycache__", ".venv", "node_modules"} for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            # Never follow symlinks outside the permitted tree.
            safe_path(root, path.relative_to(root).as_posix())
            yield path


def scan_secrets(root: Path) -> list[dict]:
    diagnostics = []
    for path in content_files(root):
        try:
            data = path.read_bytes()
            if b"\x00" in data[:8192]:
                continue
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if has_secret(text):
            diagnostics.append({"code": "possible_secret", "path": path.relative_to(root).as_posix(), "severity": "error"})
    return diagnostics


def link_errors(root: Path) -> list[dict]:
    pages = list((root / "wiki").rglob("*.md"))
    stems = {}
    for page in pages:
        stems.setdefault(page.stem, []).append(page)
    errors = []
    for page in pages:
        safe_path(root, page.relative_to(root).as_posix())
        text = page.read_text(encoding="utf-8")
        # Code examples do not create links.
        text = re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*$", "", text)
        for target in re.findall(r"\[\[([^\]]+)\]\]", text):
            name = target.split("|", 1)[0].split("#", 1)[0].strip().removesuffix(".md")
            if not name:
                continue
            candidates = stems.get(name, []) if "/" not in name else []
            try:
                exact = safe_path(root / "wiki", name + ".md")
                if "/" in name:
                    candidates = [exact] if exact.is_file() else []
                if len(candidates) != 1:
                    raise WikiError("ambiguous or broken wikilink")
            except WikiError:
                errors.append({"code": "ambiguous_or_broken_wikilink", "path": page.relative_to(root).as_posix(), "severity": "error"})
        for target in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", text):
            target = target.strip().split(' "', 1)[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            try:
                target = unquote(target.split("#", 1)[0])
                if not target:
                    continue
                resolved = (page.parent / target).resolve()
                safe_path(root, resolved.relative_to(root).as_posix())
                if not resolved.exists():
                    raise WikiError("missing link")
            except (ValueError, WikiError):
                errors.append({"code": "broken_markdown_link", "path": page.relative_to(root).as_posix(), "severity": "error"})
    return errors
