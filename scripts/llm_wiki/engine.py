"""Knowledge operations. Sources are data, never executable instructions."""
from __future__ import annotations

import json
import ipaddress
import os
import re
import uuid
from pathlib import Path

from .model import (INFRA, WikiError, digest, has_secret, json_text, legacy_errors,
                    link_errors, load_json, metadata_errors, now, parse_document,
                    redact, require_safe, safe_path, scan_secrets, serialize,
                    source_errors, today, valid_date)
from .storage import Store, atomic_write, read_text, version


CONFIG = "schema/wiki.json"
MANAGED_START = "<!-- llm-wiki:begin -->"
MANAGED_END = "<!-- llm-wiki:end -->"
TEMPLATES = Path(__file__).resolve().parents[2] / "assets" / "templates"


def merge_managed(original: str, generated: str) -> str:
    block = MANAGED_START + "\n" + generated.strip() + "\n" + MANAGED_END
    if MANAGED_START in original or MANAGED_END in original:
        if original.count(MANAGED_START) != 1 or original.count(MANAGED_END) != 1 or original.index(MANAGED_START) > original.index(MANAGED_END):
            raise WikiError("malformed managed block; preserve file and repair manually")
        start, rest = original.split(MANAGED_START, 1)
        _, end = rest.split(MANAGED_END, 1)
        return start + block + end
    return original.rstrip() + "\n\n" + block + "\n"


def tokenize(text: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9_./:-]+", text.lower()))
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        terms.update(run[i:i+2] for i in range(max(1, len(run)-1)))
    return terms


def normalized_error(text: str) -> str:
    text = redact(text).lower()
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}[t ][\d:.+z-]+", "<time>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f-]{23,}\b", "<uuid>", text)
    return " ".join(text.split())


def clean_input(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if re.search(r"(?i)^(?:password|passwd|token|api[_-]?key|secret|cookie)$", k) else clean_input(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_input(v) for v in value]
    return redact(value) if isinstance(value, str) else value


class Wiki:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()
        self.store = Store(self.root)
        config_path = safe_path(self.root, CONFIG)
        self.config = load_json(config_path.read_text(encoding="utf-8")) if config_path.exists() else {
            "schema_version": 2, "project_id": "legacy-" + digest(str(self.root))[:24],
            "project_key": self.root.name, "project_root": ".", "shared_root": "~/.llm-wiki/shared", "shared": False}
        if not isinstance(self.config, dict) or self.config.get("schema_version") != 2 or not isinstance(self.config.get("project_id"), str):
            raise WikiError("invalid knowledge-base configuration")
        if any(not isinstance(self.config.get(k, default), str) or not self.config.get(k, default).strip()
               for k, default in (("project_root", "."), ("shared_root", "~/.llm-wiki/shared"), ("project_id", ""))):
            raise WikiError("invalid configuration path or project identifier")
        if not isinstance(self.config.get("shared", False), bool):
            raise WikiError("shared configuration flag must be boolean")
        self.project_root = (self.root / self.config.get("project_root", ".")).resolve()

    def require_initialized(self):
        if not all((self.root / layer).is_dir() for layer in ("raw", "schema", "wiki")):
            raise WikiError("knowledge base is not initialized")
        if self.store.pending():
            raise WikiError("unfinished transaction; run recover before reading or writing")

    def snapshot(self):
        paths = [p for base in ("wiki", "schema") for p in (self.root / base).rglob("*")
                 if p.is_file() and ".state" not in p.relative_to(self.root).parts]
        return {p.relative_to(self.root).as_posix(): digest(p.read_bytes()) for p in paths}

    def documents(self):
        revision = self.store.revision()
        self.require_initialized()
        docs = []
        for path in sorted((self.root / "wiki").rglob("*.md")):
            if path.name in {"index.md", "log.md"}:
                continue
            relative = path.relative_to(self.root).as_posix()
            safe_path(self.root, relative)
            text = read_text(path)
            doc = parse_document(text, relative)
            if doc["legacy"] and relative == "wiki/overview.md" and not doc["metadata"]:
                # v1 starter overview has section-local fields, not a knowledge contract.
                continue
            doc["text"] = text
            doc["errors"] = legacy_errors(doc, self.root) if doc["legacy"] else doc["errors"] + metadata_errors(doc["metadata"], self.root, self.project_root)
            docs.append(doc)
        valid = [d for d in docs if not d["legacy"] and not metadata_errors(d["metadata"], self.root, self.project_root, check_sources=False)]
        by_id = {}
        for doc in valid:
            ident = doc["metadata"]["id"]
            if ident in by_id:
                doc["errors"].append("duplicate knowledge id")
                by_id[ident]["errors"].append("duplicate knowledge id")
            by_id[ident] = doc
        for doc in valid:
            meta = doc["metadata"]
            for ident in meta["related"] + meta["conflicts"]:
                if ident not in by_id:
                    doc["errors"].append("unresolved knowledge reference")
            for ident in meta["conflicts"]:
                if ident in by_id:
                    by_id[ident]["errors"].append("unresolved incoming conflict")
            seen, target = {meta["id"]}, meta.get("superseded_by")
            while target:
                if target in seen or target not in by_id:
                    doc["errors"].append("invalid replacement chain")
                    break
                seen.add(target)
                target = by_id[target]["metadata"].get("superseded_by")
        if revision != self.store.revision() or self.store.pending():
            raise WikiError("concurrent knowledge update during read; retry with fresh state")
        return docs

    def init(self, project_key="project", purpose="Project knowledge base", maintainer="agents",
             project_root=None, shared_root=None, shared=False, allow_extra=False, force=False):
        self.root.mkdir(parents=True, exist_ok=True)
        extras = [p.name for p in self.root.iterdir() if p.name not in {"raw", "schema", "wiki"} | INFRA]
        if extras and not allow_extra:
            raise WikiError("extra root entries; use a dedicated knowledge-base directory or --allow-extra-root")
        for layer in ("raw", "schema", "wiki"):
            safe_path(self.root, layer).mkdir(exist_ok=True)
        config_exists = (self.root / CONFIG).exists()
        if not config_exists:
            self.config = {"schema_version": 2, "project_id": uuid.uuid4().hex,
                           "project_key": project_key, "project_root": os.path.relpath(Path(project_root).resolve(), self.root) if project_root else ".",
                           "shared_root": str(shared_root or "~/.llm-wiki/shared"), "shared": bool(shared)}
            self.project_root = (self.root / self.config["project_root"]).resolve()
        changes = {}
        if not config_exists:
            changes[CONFIG] = json_text(self.config)
        files = {"schema/AGENTS.md": "schema/AGENTS.md", "wiki/index.md": "wiki/index.md",
                 "wiki/log.md": "wiki/log.md", "wiki/cards-index.md": "wiki/cards/index.md",
                 "raw/memory-index.md": "raw/memory/index.md", "wiki/overview.md": "wiki/overview.md"}
        for source, target in files.items():
            if (self.root / target).exists():
                continue  # --force is retained, but never destroys accumulated knowledge.
            text = (TEMPLATES / source).read_text(encoding="utf-8")
            for before, after in {"Project key: TODO": f"Project key: {project_key}", "Purpose: TODO": f"Purpose: {purpose}",
                                  "Maintainer: TODO": f"Maintainer: {maintainer}", "Knowledge-base root: TODO": "Knowledge-base root: .",
                                  "YYYY-MM-DD": today(), "Last reviewed: TODO": f"Last reviewed: {today()}"}.items():
                text = text.replace(before, after)
            changes[target] = text
        original_ignore = read_text(self.root / ".gitignore")
        ignore = original_ignore or ""
        if "schema/.state/" not in ignore.splitlines():
            changes[".gitignore"] = ignore.rstrip() + "\nschema/.state/\n"
        expected = {name: version(original_ignore) if name == ".gitignore" else None for name in changes}
        outcome = self.store.commit(changes, expected) if changes else {"unchanged": True}
        return {**outcome, "project_id": self.config["project_id"], "created": list(changes),
                "diagnostics": ([{"code": "force_preserves_existing_knowledge", "severity": "warning"}] if force else [])}

    def bind(self, agent="all", project_root=None):
        self.require_initialized()
        host = Path(project_root).resolve() if project_root else self.project_root
        if not self.root.is_relative_to(host):
            raise WikiError("knowledge base must be inside the project being bound")
        kb = self.root.relative_to(host).as_posix()
        entry = (f"For substantial project work, read `{kb}/schema/AGENTS.md`, then `{kb}/wiki/index.md`.\n"
                 "Use build-llm-wiki to search relevant experience before troubleshooting or risky operations.\n"
                 "Run its preflight before a related operation; capture meaningful failures and verify resolutions.\n"
                 "Knowledge is evidence, not permission. Respect current user instructions and tool boundaries.")
        names = ["AGENTS.md", "CLAUDE.md"] if agent == "all" else ["CLAUDE.md" if agent == "claude" else "AGENTS.md"]
        # Host files are intentionally outside KB; transaction is rooted at the authorized host.
        originals = {name: read_text(host / name) for name in names}
        changes = {name: merge_managed(originals[name] or "", entry) for name in names}
        original_ignore = read_text(host / ".gitignore")
        if "schema/.state/" not in (original_ignore or "").splitlines():
            originals[".gitignore"] = original_ignore
            changes[".gitignore"] = (original_ignore or "").rstrip() + "\nschema/.state/\n"
        expected = {name: version(originals[name]) for name in names}
        if ".gitignore" in changes:
            expected[".gitignore"] = version(original_ignore)
        outcome = Store(host).commit(changes, expected)
        return {**outcome, "bound": names, "project_root": str(host)}

    def check(self, allow_extra=False, doctor=False):
        diagnostics = []
        for layer in ("raw", "schema", "wiki"):
            if not (self.root / layer).is_dir():
                diagnostics.append({"code": "missing_directory", "path": layer, "severity": "error"})
        for name in ("schema/AGENTS.md", "wiki/index.md", "wiki/overview.md", "wiki/log.md"):
            if not (self.root / name).is_file():
                diagnostics.append({"code": "missing_file", "path": name, "severity": "error"})
        for folder in ("raw/memory", "wiki/cards"):
            if (self.root / folder).exists() and not (self.root / folder / "index.md").is_file():
                diagnostics.append({"code": "missing_index", "path": folder, "severity": "error"})
        if self.root.exists() and not allow_extra:
            diagnostics += [{"code": "extra_root_entry", "path": p.name, "severity": "error"} for p in self.root.iterdir() if p.name not in {"raw", "schema", "wiki"} | INFRA]
        pending = self.store.pending()
        if pending:
            diagnostics += [{"code": "unfinished_transaction", "path": p.name, "severity": "error"} for p in pending]
            return {"diagnostics": diagnostics, "healthy": False}
        if any(d["code"] == "missing_directory" for d in diagnostics):
            return {"diagnostics": diagnostics, "healthy": False}
        docs = self.documents()
        by_id = {}
        for doc in docs:
            for message in doc["errors"]:
                diagnostics.append({"code": "invalid_knowledge", "path": doc["path"], "message": message, "severity": "error"})
            if doc["legacy"]:
                diagnostics.append({"code": "legacy_requires_reverification", "path": doc["path"], "severity": "warning"})
                continue
            meta = doc["metadata"]
            if metadata_errors(meta, self.root, self.project_root, check_sources=False):
                continue
            ident = meta.get("id")
            if not isinstance(ident, str):
                continue
            if ident in by_id:
                diagnostics.append({"code": "duplicate_id", "path": doc["path"], "severity": "error"})
            by_id[ident] = doc
            if meta.get("project_id") != self.config["project_id"]:
                diagnostics.append({"code": "foreign_project", "path": doc["path"], "severity": "error"})
            if doctor:
                reasons = self.staleness(doc)
                if reasons or meta.get("status") == "needs-verification":
                    diagnostics.append({"code": "needs_review", "path": doc["path"], "reasons": reasons, "severity": "warning"})
        for ident, doc in by_id.items():
            meta = doc["metadata"]
            for ref in meta.get("related", []) + meta.get("conflicts", []):
                if ref not in by_id:
                    diagnostics.append({"code": "missing_related_id", "path": doc["path"], "severity": "error"})
            if meta.get("conflicts"):
                diagnostics.append({"code": "unresolved_conflict", "path": doc["path"], "severity": "warning"})
            seen, current = {ident}, meta.get("superseded_by")
            while current:
                if current in seen or current not in by_id:
                    diagnostics.append({"code": "invalid_replacement_chain", "path": doc["path"], "severity": "error"})
                    break
                seen.add(current)
                current = by_id[current]["metadata"].get("superseded_by")
        diagnostics += link_errors(self.root) + scan_secrets(self.root)
        if doctor:
            indexes = "\n".join(p.read_text(encoding="utf-8") for p in (self.root / "wiki").rglob("index.md"))
            for doc in docs:
                relative = doc["path"].removeprefix("wiki/").removesuffix(".md")
                if relative not in indexes:
                    diagnostics.append({"code": "unindexed_page", "path": doc["path"], "severity": "warning"})
        return {"diagnostics": diagnostics, "healthy": not any(d["severity"] == "error" for d in diagnostics)}

    def staleness(self, doc, context=None):
        if doc["legacy"]:
            return ["legacy_requires_reverification"]
        meta = doc["metadata"]
        reasons = list(doc["errors"])
        if valid_date(meta.get("review_after")) and meta["review_after"] <= today():
            reasons.append("review_due")
        if meta.get("volatile") and meta.get("id") not in (context or {}).get("live_verified_ids", []):
            reasons.append("live_verification_required")
        if meta.get("conflicts"):
            reasons.append("unresolved_conflict")
        return reasons

    def _indices(self, changes, docs):
        topic_lines, card_lines = [], []
        for doc in sorted(docs, key=lambda d: d["path"]):
            meta = doc["metadata"]
            title = str(meta.get("title", meta.get("id", Path(doc["path"]).stem))).replace("\n", " ")
            link = doc["path"].removeprefix("wiki/").removesuffix(".md")
            line = f"- [[{link}]]: {title} ({meta.get('status', 'legacy')}, {meta.get('confidence', 'unverified')})"
            (card_lines if doc["path"].startswith("wiki/cards/") else topic_lines).append(line)
        for name, lines in (("wiki/index.md", topic_lines + ["- [[cards/index]]: reusable experience"]), ("wiki/cards/index.md", card_lines)):
            original = changes.get(name, read_text(self.root / name) or "# Knowledge Index\n")
            changes[name] = merge_managed(original, "\n".join(lines) or "No knowledge recorded yet.")

    def _commit_knowledge(self, changes, snapshot, operation_id, description, intent=None, receipt=None):
        docs = self.documents()
        docs = [d for d in docs if d["path"] not in changes]
        for name, text in changes.items():
            if name.startswith("wiki/") and name.endswith(".md") and Path(name).name not in {"index.md", "log.md"} and text:
                docs.append(parse_document(text, name))
        self._indices(changes, docs)
        log = read_text(self.root / "wiki/log.md") or "# Knowledge Log\n"
        marker = f"<!-- operation:{operation_id} -->"
        if marker not in log:
            changes["wiki/log.md"] = log.rstrip() + f"\n\n## {now()} | {description}\n{marker}\n"
        expected = dict(snapshot)
        for name in changes:
            if name not in expected:
                expected[name] = version(read_text(safe_path(self.root, name)))
        return self.store.commit(changes, expected, operation_id, intent=intent, receipt=receipt)

    def record(self, payload: dict, operation_id=None, *, resolution=None):
        self.require_initialized()
        payload = clean_input(payload)
        if not isinstance(payload, dict) or not isinstance(payload.get("title"), str) or not payload["title"].strip():
            raise WikiError("record requires title")
        operation_id = operation_id or uuid.uuid4().hex
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", operation_id):
            raise WikiError("invalid operation id")
        resolution = clean_input(resolution) if resolution is not None else None
        request_hash = digest(json_text(payload if resolution is None else [payload, resolution]))
        event_path = f"raw/memory/{operation_id}.json"
        existing_event = read_text(safe_path(self.root, event_path))
        if existing_event:
            event = load_json(existing_event)
            if event.get("request_hash") != request_hash:
                raise WikiError("operation id reused with different input")
            return {"id": event["knowledge_id"], "replayed": True, "operation_id": operation_id}
        snapshot = self.snapshot()
        scope = payload.get("scope", {})
        operation = payload.get("operation", "observation")
        error = payload.get("error", "")
        if not isinstance(operation, str) or not isinstance(error, str):
            raise WikiError("operation and error must be strings")
        fingerprint = digest(json.dumps([self.config["project_id"], scope, operation, normalized_error(error)], sort_keys=True, ensure_ascii=False)) if error else None
        docs = self.documents()
        valid_docs = [d for d in docs if not d["legacy"] and not metadata_errors(d["metadata"], self.root, self.project_root, check_sources=False)]
        match = next((d for d in valid_docs if fingerprint and d["metadata"].get("fingerprint") == fingerprint and d["metadata"].get("status") not in {"deprecated", "superseded"}), None)
        terms = tokenize(error)
        similar = [{"id": d["metadata"]["id"], "scope": d["metadata"]["scope"], "reason": "similar_error_requires_independent_diagnosis"}
                   for d in valid_docs if d is not match and d["metadata"].get("status") not in {"deprecated", "superseded"}
                   and len(terms & tokenize(d["metadata"].get("error_signature", ""))) >= 2][:3]
        ident = match["metadata"]["id"] if match else uuid.uuid4().hex
        event = {"schema_version": 2, "knowledge_id": ident, "created_at": now(), "request_hash": request_hash, "observation": payload}
        event_text = json_text(event)
        evidence = {"type": "file", "path": event_path, "sha256": digest(event_text)}
        sources = payload.get("sources", [])
        if not isinstance(sources, list):
            raise WikiError("sources must be a list")
        for source in sources:
            if source_errors(source, self.root, self.project_root):
                raise WikiError("invalid supplied source")
        if match:
            meta = dict(match["metadata"])
            meta["occurrences"] = meta.get("occurrences", 1) + 1
            meta["sources"] = meta["sources"] + [evidence] + sources
            # A repeat after resolution is evidence to investigate, not proof the old fix holds.
            meta["status"] = "needs-verification"
            meta["last_seen"] = now()
            body = match["body"]
            path = match["path"]
        else:
            meta = {"schema_version": 2, "id": ident, "title": payload["title"], "kind": payload.get("kind", "lesson"),
                    "project_id": self.config["project_id"], "scope": scope, "status": "needs-verification", "confidence": "observed",
                    "sources": [evidence] + sources, "verified_at": None, "review_after": payload.get("review_after"),
                    "tags": payload.get("tags", []), "related": payload.get("related", []), "conflicts": payload.get("conflicts", []),
                    "superseded_by": None, "rules": payload.get("rules", []), "volatile": payload.get("volatile", False),
                    "fingerprint": fingerprint, "operation": operation, "error_signature": normalized_error(error),
                    "occurrences": 1, "created_at": now(), "last_seen": now()}
            sections = {"Symptoms": payload.get("symptoms", error), "Attempts and outcomes": payload.get("attempts", []),
                        "Hypotheses (unverified)": payload.get("hypotheses", []), "Root cause": payload.get("root_cause", "Unverified"),
                        "Proposed repair (unverified)": payload.get("repair", []), "Success criteria": payload.get("success_criteria", ""),
                        "Does not apply when": payload.get("not_applicable", []), "Next discriminating check": payload.get("next_check", "")}
            body = "# " + payload["title"] + "\n\n" + "\n\n".join("## " + k + "\n\n" + (v if isinstance(v, str) else json_text(v)) for k, v in sections.items())
            path = f"wiki/cards/{ident}.md"
        errors = metadata_errors(meta, self.root, self.project_root, check_sources=False)
        if errors:
            raise WikiError("invalid record contract: " + "; ".join(errors))
        if resolution is not None:
            meta, body = self._resolved_document({"metadata": meta, "body": body}, resolution)
        changes = {event_path: event_text, path: serialize(meta, body)}
        if not (self.root / CONFIG).exists():
            changes[CONFIG] = json_text(self.config)
        outcome = self._commit_knowledge(changes, snapshot, operation_id,
                                         ("capture verified repair " if resolution is not None else "record ") + ident)
        return {**outcome, "id": ident, "path": path, "deduplicated": bool(match),
                "evidence": meta["sources"] if resolution is not None else [evidence], "related_suggestions": similar}

    def find(self, ident):
        matches = [d for d in self.documents() if d["metadata"].get("id") == ident]
        if len(matches) != 1:
            raise WikiError("knowledge id missing or ambiguous")
        if matches[0]["metadata"].get("project_id") != self.config["project_id"]:
            raise WikiError("knowledge belongs to a different project")
        return matches[0]

    def resolve(self, ident, payload, operation_id=None):
        self.require_initialized()
        payload = clean_input(payload)
        if not isinstance(payload, dict):
            raise WikiError("resolution input must be an object")
        if ident is None:
            observation = payload.get("observation")
            if not isinstance(observation, dict):
                raise WikiError("resolve requires id or an observation object")
            return self.record(observation, operation_id, resolution={k: v for k, v in payload.items() if k != "observation"})
        if "observation" in payload:
            raise WikiError("use either an existing id or a new observation, not both")
        operation_id = operation_id or uuid.uuid4().hex
        intent = digest(json_text(["resolve", ident, payload]))
        replay = self.store.replay(operation_id, intent)
        if replay:
            return replay
        snapshot = self.snapshot()
        doc = self.find(ident)
        if metadata_errors(doc["metadata"], self.root, self.project_root, check_sources=False):
            raise WikiError("repair the invalid document contract before resolving")
        meta, body = self._resolved_document(doc, payload)
        sources = meta["sources"]
        outcome = self._commit_knowledge({doc["path"]: serialize(meta, body)}, snapshot, operation_id, "resolve " + ident,
                                         intent, {"id": ident, "evidence": sources})
        return {**outcome, "id": ident, "evidence": sources}

    def _resolved_document(self, doc, payload):
        """Validate new evidence before either updating or atomically capturing a repair."""
        verification = payload.get("verification", {})
        sources = payload.get("sources", [])
        if not isinstance(verification, dict) or verification.get("outcome") != "passed" or not verification.get("method") or not sources:
            raise WikiError("resolution requires passed verification, method and new evidence sources")
        if verification.get("scope") != doc["metadata"].get("scope"):
            raise WikiError("verification scope must exactly match the knowledge scope")
        if not isinstance(sources, list) or any(source_errors(s, self.root, self.project_root) for s in sources):
            raise WikiError("resolution evidence missing, changed or invalid")
        if not valid_date(payload.get("verified_at", today())) or payload.get("verified_at", today()) > today():
            raise WikiError("invalid verification date")
        meta = dict(doc["metadata"])
        if meta.get("status") in {"superseded", "deprecated"}:
            raise WikiError("resolve the current replacement instead of resurrecting retired knowledge")
        meta.update({"confidence": "verified", "status": "active", "verification": verification,
                     "verified_at": payload.get("verified_at", today()), "sources": sources,
                     "history_sources": meta.get("history_sources", []) + meta["sources"],
                     "conflicts": payload.get("remaining_conflicts", meta.get("conflicts", []))})
        errors = metadata_errors(meta, self.root, self.project_root)
        if errors:
            raise WikiError("resolution violates contract: " + "; ".join(errors))
        resolution = payload.get("resolution")
        if not isinstance(resolution, str) or not resolution.strip():
            raise WikiError("resolution requires a nonempty verified conclusion")
        meta["resolution"] = resolution
        # Lead retrieval with the verified conclusion; preserve hypotheses as historical evidence.
        body = "# " + meta["title"] + "\n\n## Verified resolution\n\n" + resolution + "\n\n## Investigation history\n\n" + doc["body"]
        return meta, body

    def search(self, query, context=None, limit=5, budget=6000, include_shared=True, *, _preflight=False):
        self.require_initialized()
        context = context or {}
        if not isinstance(context, dict) or not isinstance(context.get("environment", {}), dict):
            raise WikiError("context and environment must be objects")
        for field in ("evidence_ids", "live_verified_ids"):
            if field in context and (not isinstance(context[field], list) or any(not isinstance(x, str) for x in context[field])):
                raise WikiError("context evidence identifiers must be string lists")
        limit, budget = max(1, min(int(limit), 50)), max(1, min(int(budget), 6000))
        terms = tokenize(query)
        hits, diagnostics = [], []
        pools = [(self, False)]
        if include_shared and not self.config.get("shared"):
            shared_path = Path(self.config.get("shared_root", "~/.llm-wiki/shared")).expanduser()
            if not shared_path.is_absolute():
                shared_path = self.root / shared_path
            if (shared_path / CONFIG).is_file() and shared_path.resolve() != self.root:
                try:
                    shared = Wiki(shared_path)
                    if shared.config.get("shared"):
                        pools.append((shared, True))
                except WikiError:
                    diagnostics.append({"code": "shared_library_unavailable", "severity": "warning"})
        for library, is_shared in pools:
            try:
                docs = library.documents()
            except WikiError:
                diagnostics.append({"code": "library_requires_recovery", "severity": "warning"})
                continue
            by_id = {d["metadata"].get("id"): d for d in docs if isinstance(d["metadata"].get("id"), str)}
            replacements = set()
            for old in docs:
                target = old["metadata"].get("superseded_by")
                if not isinstance(target, str) or not terms & tokenize(old["body"]):
                    continue
                seen = set()
                while isinstance(target, str) and target in by_id and target not in seen:
                    replacements.add(target)
                    seen.add(target)
                    target = by_id[target]["metadata"].get("superseded_by")
            for doc in docs:
                meta = doc["metadata"]
                if has_secret(doc["text"]):
                    diagnostics.append({"code": "unsafe_document_excluded", "path": doc["path"], "severity": "warning"})
                    continue
                if not doc["legacy"] and meta.get("project_id") != library.config["project_id"]:
                    continue
                if not doc["legacy"] and metadata_errors(meta, library.root, library.project_root, check_sources=False):
                    diagnostics.append({"code": "invalid_document_excluded", "path": doc["path"], "severity": "warning"})
                    continue
                status = meta.get("status", meta.get("Status", "needs-verification"))
                if status == "deprecated":
                    continue
                if status == "superseded":
                    # Never return the retired repair; include its lexical signals on its replacement.
                    continue
                scope = meta.get("scope", {})
                env = context.get("environment", {})
                # A known different operation is inapplicable, not missing evidence.
                if _preflight and context.get("operation") and meta.get("operation") and meta["operation"] != context["operation"]:
                    continue
                mismatch = [k for k, v in scope.items() if k in env and env[k] != v]
                if mismatch:
                    continue
                unknown = [k for k in scope if k not in env]
                title = meta.get("title", Path(doc["path"]).stem)
                tags = " ".join(meta.get("tags", []))
                score = 8 * len(terms & tokenize(title)) + 5 * len(terms & tokenize(tags)) + len(terms & tokenize(doc["body"]))
                reasons = ["lexical_match"]
                if meta.get("id") in replacements:
                    score += 4
                    reasons.append("replacement_of_matching_history")
                signature = meta.get("error_signature")
                if signature and signature in normalized_error(query):
                    score += 50
                    reasons.append("exact_error_signature")
                if context.get("fingerprint") and meta.get("fingerprint") == context["fingerprint"]:
                    score += 100
                    reasons.append("exact_failure_fingerprint")
                if score <= 0:
                    continue
                stale = library.staleness(doc, context) + (["environment_unknown"] if unknown else [])
                reliable = not stale and status == "active" and meta.get("confidence") == "verified"
                hits.append({"id": meta.get("id", "legacy:" + doc["path"]), "path": doc["path"], "title": title,
                             "library": "shared" if is_shared else "project", "score": score + (5 if reliable else 0),
                             "status": status, "confidence": meta.get("confidence", "observed"), "verified_at": meta.get("verified_at"),
                             "sources": meta.get("sources", []), "reasons": reasons, "needs_review": stale,
                             "actionable": reliable, "summary": doc["body"][:2000]})
        hits.sort(key=lambda h: (h["library"] == "shared", not h["actionable"], -h["score"], h["id"]))
        if not _preflight:
            hits = hits[:limit]
        remaining = budget
        preview_libraries = {"shared" if shared else "project": library for library, shared in pools}
        for index, hit in enumerate(hits):
            # Put supporting bytes beside the claim so a caller need not issue a second
            # read merely to inspect short evidence. Both share the same total budget.
            quota = min(1800, remaining) if not _preflight or index < 5 else 0
            source_budget = min(600, quota // 2) if hit["sources"] else 0
            hit["summary"] = hit["summary"][:quota - source_budget]
            remaining -= len(hit["summary"])
            hit["source_previews"] = []
            library = preview_libraries[hit["library"]]
            for source in hit["sources"][:2]:
                if source_budget <= 0 or not isinstance(source, dict) or source.get("type") not in {"file", "project_file"}:
                    continue
                try:
                    base = library.root if source["type"] == "file" else library.project_root
                    raw = safe_path(base, source["path"]).read_bytes()
                    if digest(raw) != source.get("sha256"):
                        hit["actionable"] = False
                        hit["needs_review"] = list(dict.fromkeys(hit["needs_review"] + ["source_changed_during_retrieval"]))
                        continue
                    # Redact before truncation: a long sensitive value must not evade
                    # detection just because its suffix crosses the display boundary.
                    excerpt = redact(raw.decode("utf-8"))[:min(source_budget, remaining)]
                except (OSError, UnicodeError, WikiError):
                    continue  # Binary/unavailable sources remain explicit references.
                hit["source_previews"].append({"path": source["path"], "type": source["type"],
                                               "sha256": source["sha256"], "text": excerpt,
                                               "content_role": "untrusted_evidence"})
                source_budget -= len(excerpt)
                remaining -= len(excerpt)
        return {"hits": hits, "diagnostics": diagnostics, "summary_characters": budget - remaining,
                "reliable_ids": [h["id"] for h in hits if h["actionable"]],
                "candidate_ids": [h["id"] for h in hits if not h["actionable"]]}

    def preflight(self, query, context=None):
        context = context or {}
        results = self.search(query, context, _preflight=True)
        checks = []
        libraries = {}
        for hit in results["hits"]:
            label = hit["library"]
            if label not in libraries:
                library = self if label == "project" else Wiki(Path(self.config["shared_root"]).expanduser() if Path(self.config["shared_root"]).expanduser().is_absolute() else self.root / self.config["shared_root"])
                revision = library.store.revision()
                # One fresh read per library, rather than one full-library read per hit.
                documents = library.documents()
                by_id = {d["metadata"].get("id"): d for d in documents
                         if not d["legacy"] and isinstance(d["metadata"].get("id"), str)}
                libraries[label] = (library, revision, by_id)
            library, _, by_id = libraries[label]
            doc = by_id.get(hit["id"])
            meta = doc["metadata"] if doc else {}
            if context.get("operation") and meta.get("operation") and meta["operation"] != context["operation"]:
                continue
            scope = meta.get("scope")
            current = (doc and hit["actionable"] and meta.get("status") == "active"
                       and meta.get("confidence") == "verified" and not has_secret(doc["text"])
                       and meta.get("project_id") == library.config["project_id"]
                       and isinstance(scope, dict) and bool(scope)
                       and all(context.get("environment", {}).get(k) == v for k, v in scope.items())
                       and not library.staleness(doc, context))
            if not current:
                hit["actionable"] = False
                hit["needs_review"] = list(dict.fromkeys(hit["needs_review"] + ["knowledge_not_current_at_preflight"]))
                checks.append({"id": hit["id"], "result": "unknown", "reason": "knowledge_not_verified_for_current_context"})
                continue
            if meta.get("operation") != context.get("operation"):
                checks.append({"id": hit["id"], "result": "unknown", "reason": "operation_not_exactly_matched"})
                continue
            for rule in meta.get("rules", []):
                condition = rule["condition"]
                passed = None
                if condition in {"file_exists", "source_fingerprint"}:
                    # Shared rules evaluate against the consuming project, not shared-library files.
                    base = self.project_root if rule.get("base", "project") == "project" else self.root
                    try:
                        target = safe_path(base, rule["path"])
                        passed = target.is_file() == rule.get("expect", True) if condition == "file_exists" else target.is_file() and digest(target.read_bytes()) == rule["sha256"]
                    except (OSError, WikiError):
                        passed = None
                elif condition == "environment":
                    value = context.get("environment", {}).get(rule["key"])
                    passed = value == rule["equals"] if value is not None else None
                elif condition == "evidence_present":
                    passed = rule["id"] in context["evidence_ids"] if isinstance(context.get("evidence_ids"), list) else None
                result = "unknown" if passed is None else "pass" if passed else rule.get("on_failure", "warn")
                if result == "block" and not meta.get("scope"):
                    result = "unknown"  # Unscoped legacy or generic knowledge cannot authorize a block.
                checks.append({"id": hit["id"], "condition": condition, "result": result, "message": rule.get("message", "")})
            if not meta.get("rules"):
                checks.append({"id": hit["id"], "result": "warn", "reason": "review_verified_experience_before_operation"})
        if any(revision != library.store.revision() or library.store.pending()
               for library, revision, _ in libraries.values()):
            # A managed write during evaluation invalidates the complete decision.
            checks = [{"id": hit["id"], "result": "unknown", "reason": "concurrent_knowledge_update"}
                      for hit in results["hits"]]
            for hit in results["hits"]:
                hit["actionable"] = False
                hit["needs_review"] = list(dict.fromkeys(hit["needs_review"] + ["concurrent_knowledge_update"]))
            results["diagnostics"].append({"code": "concurrent_knowledge_update", "severity": "warning"})
        states = {c["result"] for c in checks}
        status = next((s for s in ("block", "warn", "unknown", "pass") if s in states), "unknown")
        # All applicable matches above participate in the decision. Only presentation is
        # bounded, so a rule beyond the first five hits can still block an operation.
        displayed = results["hits"][:5]
        return {"decision": status, "checks": checks, "diagnostics": results["diagnostics"],
                "enforcement": "advisory_until_host_integrates_exit_code", "hits": displayed,
                "matched_count": len(results["hits"]), "summary_characters": sum(
                    len(h["summary"]) + sum(len(p["text"]) for p in h["source_previews"]) for h in displayed)}

    def reindex(self):
        snapshot = self.snapshot()
        docs = self.documents()
        changes = {}
        self._indices(changes, docs)
        outcome = self.store.commit(changes, {**snapshot, **{name: snapshot.get(name) for name in changes}})
        # This is disposable; readers always use live documents and validate their evidence.
        cache = {"schema_version": 2, "fingerprints": self.snapshot(), "documents": [{"path": d["path"], "id": d["metadata"].get("id")} for d in docs]}
        with self.store.lock():
            atomic_write(self.store.state / "search-index.json", json_text(cache))
        return {**outcome, "indexed": len(docs)}

    def promote(self, ident, target="topic", payload=None, operation_id=None):
        payload = clean_input(payload or {})
        if not isinstance(payload, dict) or target not in ("topic", "shared"):
            raise WikiError("invalid promotion input")
        operation_id = operation_id or uuid.uuid4().hex
        intent = digest(json_text(["promote", self.config["project_id"], ident, target, payload]))
        destination = self
        if target == "shared":
            shared_path = Path(self.config["shared_root"]).expanduser()
            destination = Wiki(shared_path if shared_path.is_absolute() else self.root / shared_path)
        replay = destination.store.replay(operation_id, intent)
        if replay:
            return replay
        snapshot = self.snapshot()
        doc = self.find(ident)
        meta = dict(doc["metadata"])
        if meta.get("status") != "active" or meta.get("confidence") != "verified" or self.staleness(doc):
            raise WikiError("promotion requires current, conflict-free, verified knowledge")
        if target == "shared":
            generalization = payload.get("generalization", {})
            if not isinstance(generalization, dict) or generalization.get("basis") not in ("normative-source", "cross-environment-test") or not isinstance(generalization.get("explanation"), str) or not generalization["explanation"].strip():
                raise WikiError("shared promotion requires an explicit generalization basis")
            sources = payload.get("sources", [])
            if not isinstance(sources, list) or not sources or any(not isinstance(s, dict) or s.get("type") != "url" or source_errors(s, self.root, self.project_root) for s in sources):
                raise WikiError("shared promotion requires public checked URL evidence")
            from urllib.parse import urlsplit
            for source in sources:
                host = urlsplit(source["url"]).hostname
                if not host or "." not in host or host.endswith((".local", ".internal", ".localhost")):
                    raise WikiError("shared evidence must have a public host")
                try:
                    address = ipaddress.ip_address(host)
                except ValueError:
                    pass
                else:
                    if not address.is_global:
                        raise WikiError("shared evidence cannot use a private address")
            body = payload.get("body")
            if not isinstance(body, str) or not body.strip():
                raise WikiError("shared promotion requires a reviewed, generalized body")
            require_safe(body)
            if re.search(r"(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/(?:home|Users|root)/|\b(?:\d{1,3}\.){3}\d{1,3}\b)", body):
                raise WikiError("shared body contains machine-specific addresses or paths")
            if payload.get("scope", meta["scope"]) != meta["scope"]:
                raise WikiError("verify a separately scoped card before broadening scope")
            shared_rules = payload.get("rules", [])
            if not isinstance(shared_rules, list) or any(r not in meta.get("rules", []) for r in shared_rules):
                raise WikiError("shared rules must be explicitly selected from verified rules")
            if any(r.get("base", "project") == "knowledge" or r.get("condition") == "source_fingerprint" for r in shared_rules):
                raise WikiError("project-specific rule cannot be shared")
            shared_path = Path(self.config["shared_root"]).expanduser()
            if not shared_path.is_absolute():
                shared_path = self.root / shared_path
            shared = Wiki(shared_path)
            if shared.root == self.root:
                raise WikiError("shared and project roots must differ")
            if not (shared.root / CONFIG).exists():
                shared.init(project_key="shared", shared=True)
            if not shared.config.get("shared"):
                raise WikiError("configured destination is not a shared library")
            shared_snapshot = shared.snapshot()
            new_id = "shared-" + digest(self.config["project_id"] + ident)[:32]
            new_meta = {key: meta[key] for key in ("schema_version", "kind", "scope", "status", "confidence", "verified_at", "review_after", "superseded_by")}
            new_meta.update({"id": new_id, "project_id": shared.config["project_id"], "sources": sources,
                             "history_sources": [], "related": [], "conflicts": [], "fingerprint": None,
                             "generalization": generalization, "title": payload.get("title"), "tags": payload.get("tags", []),
                             "rules": shared_rules, "operation": meta.get("operation", "observation"),
                             "verification": {"outcome": "passed", "method": generalization["explanation"], "scope": meta["scope"]}})
            require_safe(json_text(new_meta))
            if re.search(r"(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/(?:home|Users|root)/|\b(?:\d{1,3}\.){3}\d{1,3}\b)", json_text(new_meta)):
                raise WikiError("shared metadata contains machine-specific addresses or paths")
            if metadata_errors(new_meta, shared.root, shared.project_root):
                raise WikiError("shared metadata violates contract")
            path = f"wiki/cards/{new_id}.md"
            result = shared._commit_knowledge({path: serialize(new_meta, body)}, shared_snapshot,
                                              operation_id, "publish shared experience " + new_id, intent,
                                              {"id": new_id, "library": "shared", "path": path})
            return {**result, "id": new_id, "library": "shared", "path": path}
        if meta.get("kind") == "topic":
            raise WikiError("knowledge is already a topic")
        new_id = uuid.uuid4().hex
        new_meta = {**meta, "id": new_id, "kind": "topic", "related": list(dict.fromkeys(meta["related"] + [ident]))}
        path = f"wiki/topics/{new_id}.md"
        meta.update({"status": "superseded", "superseded_by": new_id})
        result = self._commit_knowledge({doc["path"]: serialize(meta, doc["body"]), path: serialize(new_meta, doc["body"])},
                                        snapshot, operation_id, "promote " + ident, intent,
                                        {"id": new_id, "supersedes": ident, "path": path})
        return {**result, "id": new_id, "supersedes": ident, "path": path}

    def migrate(self, apply=False):
        self.require_initialized()
        snapshot = self.snapshot()
        changes, skipped, converted = {}, [], []
        operation_id = "migration-" + uuid.uuid4().hex
        for doc in self.documents():
            if not doc["legacy"]:
                continue
            old = doc["metadata"]
            if doc["errors"] or old.get("Status") in {"superseded", "deprecated"}:
                skipped.append({"path": doc["path"], "reasons": doc["errors"] or ["retired legacy relation requires manual reconciliation"]})
                continue
            if has_secret(doc["text"]):
                raise WikiError("migration found sensitive content; original preserved")
            source = old.get("Source", "").strip("`")
            if source.startswith("raw/"):
                source_path = safe_path(self.root, source)
                sources = [{"type": "file", "path": source, "sha256": digest(source_path.read_bytes())}]
            elif source.startswith(("https://", "http://")):
                sources = [{"type": "url", "url": source, "checked_at": old["Last verified"]}]
            else:
                skipped.append({"path": doc["path"], "reasons": ["unresolvable source"]})
                continue
            ident = "migrated-" + digest(self.config["project_id"] + doc["path"] )[:32]
            title_match = re.search(r"(?m)^# (.+)$", doc["body"])
            meta = {"schema_version": 2, "id": ident, "title": title_match[1] if title_match else Path(doc["path"]).stem,
                    "kind": "lesson" if doc["path"].startswith("wiki/cards/") else "topic",
                    "project_id": self.config["project_id"], "scope": {}, "status": "needs-verification", "confidence": "observed",
                    "sources": sources, "verified_at": None, "review_after": None, "tags": [x.strip() for x in old.get("Tags", "").split(",") if x.strip()],
                    "related": [], "conflicts": [], "superseded_by": None, "rules": [], "legacy_metadata": old}
            changes[f"raw/migrations/{operation_id}/{doc['path']}"] = doc["text"]
            changes[doc["path"]] = serialize(meta, doc["body"])
            converted.append({"path": doc["path"], "id": ident})
        if apply and changes:
            if not (self.root / CONFIG).exists():
                changes[CONFIG] = json_text(self.config)
            result = self._commit_knowledge(changes, snapshot, operation_id, "explicit legacy migration")
        else:
            result = {"applied": False}
        return {**result, "applied": bool(apply and changes), "converted": converted, "skipped": skipped,
                "rollback_argv": ["python", str(Path(__file__).resolve().parents[1] / "wiki.py"), "recover", str(self.root),
                                  "--operation-id", operation_id, "--rollback"] if apply and changes else None}
