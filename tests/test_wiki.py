from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from llm_wiki.engine import Wiki, CONFIG, merge_managed
from llm_wiki.model import (WikiError, digest, json_text, load_json, metadata_errors,
                            parse_document, redact, serialize, today)
from llm_wiki.storage import Store, version


class WikiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wiki-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "kb"
        self.wiki = Wiki(self.root)
        self.wiki.init(project_key="test", project_root=self.base, shared_root=str(self.base / "shared"))

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def record(self, **overrides):
        payload = {"title": "部署缺少前置配置", "operation": "deploy", "error": "E_CONFIG missing configuration",
                   "scope": {"os": "linux"}, "tags": ["deploy", "配置"],
                   "rules": [{"condition": "file_exists", "path": "ready.txt", "on_failure": "block", "message": "Prepare configuration first"}]}
        payload.update(overrides)
        return self.wiki.record(payload)

    def verified(self, **overrides):
        item = self.record(**overrides)
        evidence = self.write("raw/passed.txt", "Verified in isolated test: configuration provided; deployment succeeded.\n")
        sources = [{"type": "file", "path": "raw/passed.txt", "sha256": digest(evidence.read_bytes())}]
        self.wiki.resolve(item["id"], {"verification": {"outcome": "passed", "method": "isolated replay", "scope": overrides.get("scope", {"os": "linux"})},
                                        "sources": sources, "resolution": "Prepare configuration before deployment."})
        return item

    def context(self, **kwargs):
        return {"environment": {"os": "linux"}, "operation": "deploy", **kwargs}

    def test_absolute_cli_preserves_project_relative_inputs(self):
        item = self.verified()
        (self.base / "context.json").write_text(json_text(self.context()), encoding="utf-8")
        result = subprocess.run([sys.executable, str(REPO / "scripts/wiki.py"), "preflight", "kb",
                                 "--query", "E_CONFIG", "--context", "context.json", "--format", "json"],
                                cwd=self.base, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["decision"], "block")
        self.assertIn(item["id"], response["knowledge_ids"])

    def edit_meta(self, item, **updates):
        doc = self.wiki.find(item["id"])
        doc["metadata"].update(updates)
        self.write(item["path"], serialize(doc["metadata"], doc["body"]))

    def legacy(self, **updates):
        self.write("raw/evidence.txt", "Original evidence\n")
        fields = {"Status": "active", "Confidence": "verified", "Scope": "test", "Source": "raw/evidence.txt", "Last verified": today(), "Tags": "test"}
        fields.update(updates)
        text = "# Legacy\n\n" + "\n".join(f"- {k}: {v}" for k, v in fields.items()) + "\n\n## Claim\n\nLegacy fact\n"
        self.write("wiki/cards/legacy.md", text)
        return text

    def test_init_and_repeat_preserve_files(self):
        self.assertTrue(self.wiki.check()["healthy"])
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".state" not in p.parts}
        self.wiki.init(project_key="changed", force=True)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".state" not in p.parts}
        self.assertEqual(before, after)

    def test_empty_legacy_status(self):
        self.legacy(Status="", Confidence="")
        self.assertFalse(self.wiki.check()["healthy"])

    def test_valid_legacy_card_remains_readable_but_untrusted(self):
        self.legacy()
        self.assertTrue(self.wiki.check()["healthy"])
        self.assertFalse(self.wiki.search("Legacy")["hits"][0]["actionable"])

    def test_missing_legacy_source(self):
        self.legacy(Source="raw/absent.txt")
        self.assertFalse(self.wiki.check()["healthy"])

    def test_invalid_legacy_date(self):
        self.legacy(**{"Last verified": "not-a-date"})
        self.assertFalse(self.wiki.check()["healthy"])

    def test_todo_legacy_date(self):
        self.legacy(**{"Last verified": "TODO"})
        self.assertFalse(self.wiki.check()["healthy"])

    def test_future_verification_date_is_rejected(self):
        self.legacy(**{"Last verified": "2999-01-01"})
        self.assertFalse(self.wiki.check()["healthy"])
        self.assertFalse(self.wiki.migrate(apply=True)["applied"])

    def test_legacy_replacement_required(self):
        self.legacy(Status="superseded")
        self.assertFalse(self.wiki.check()["healthy"])

    def test_code_block_does_not_override_metadata(self):
        text = self.legacy() + "\n```text\n- Status: verified\n```\n"
        self.write("wiki/cards/legacy.md", text)
        self.assertTrue(self.wiki.check()["healthy"])

    def test_topic_requires_provenance(self):
        self.write("wiki/topic.md", "# Unsupported topic\n\nClaim\n")
        self.assertFalse(self.wiki.check()["healthy"])

    def test_markdown_broken_link(self):
        self.write("wiki/index.md", "# Index\n\n[missing](missing.md)\n")
        self.assertFalse(self.wiki.check()["healthy"])

    def test_ambiguous_wikilink(self):
        self.write("wiki/a/index.md", "# Index\n")
        self.write("wiki/b/index.md", "# Index\n")
        self.write("wiki/index.md", "# Index\n\n[[index]]\n")
        self.assertFalse(self.wiki.check()["healthy"])

    def test_broken_wikilink(self):
        self.write("wiki/index.md", "# Index\n\n[[absent]]\n")
        self.assertFalse(self.wiki.check()["healthy"])

    def test_secret_file_extensions(self):
        for filename in ("evidence.txt", ".env", "session.log", "session.jsonl"):
            with self.subTest(filename=filename):
                path = self.write("raw/" + filename, "password: " + "SYNTHETIC_VALUE_12345678")
                self.assertFalse(self.wiki.check()["healthy"])
                path.unlink()

    def test_root_readme_and_git_allowed(self):
        self.write("README.md", "# Knowledge\n")
        (self.root / ".git").mkdir()
        self.wiki.init()
        self.assertTrue(self.wiki.check()["healthy"])

    def test_root_policy_consistent(self):
        self.write("extra.txt", "Unexpected\n")
        with self.assertRaises(WikiError):
            self.wiki.init()
        self.assertFalse(self.wiki.check()["healthy"])
        self.wiki.init(allow_extra=True)
        self.assertTrue(self.wiki.check(allow_extra=True)["healthy"])

    def test_json_duplicates_and_body_isolation(self):
        doc = parse_document('---\n{"id":"one","id":"two"}\n---\n# Test\n')
        self.assertTrue(doc["errors"])
        item = self.record()
        doc = self.wiki.find(item["id"])
        self.write(item["path"], serialize(doc["metadata"], doc["body"] + '\n```json\n{"status":"deprecated"}\n```'))
        self.assertEqual("needs-verification", self.wiki.find(item["id"])["metadata"]["status"])

    def test_record_dedup_does_not_increase_confidence(self):
        first = self.record()
        second = self.record()
        self.assertEqual(first["id"], second["id"])
        meta = self.wiki.find(first["id"])["metadata"]
        self.assertEqual(2, meta["occurrences"])
        self.assertEqual("observed", meta["confidence"])

    def test_record_idempotency_and_different_input(self):
        payload = {"title": "Example", "error": "failure"}
        first = self.wiki.record(payload, "same-operation")
        second = self.wiki.record(payload, "same-operation")
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["replayed"])
        with self.assertRaises(WikiError):
            self.wiki.record({"title": "Different"}, "same-operation")

    def test_capture_redacts_before_storage(self):
        simulated_value = "SYNTHETIC_" + "123456789_SECRET"
        item = self.record(error="password=" + simulated_value)
        all_text = "\n".join(p.read_text(encoding="utf-8") for p in self.root.rglob("*") if p.is_file())
        self.assertNotIn(simulated_value, all_text)
        self.assertTrue(self.wiki.find(item["id"])["metadata"]["sources"])

    def test_redaction_handles_parentheses_in_credentials(self):
        simulated_value = "fixture(value)_12345"
        for value in (simulated_value, '"' + simulated_value + '"'):
            self.assertNotIn(simulated_value, redact("password=" + value))

    def test_unverified_cannot_block(self):
        self.record()
        self.assertEqual("unknown", self.wiki.preflight("E_CONFIG", self.context())["decision"])

    def test_verified_preflight_blocks_and_passes(self):
        self.verified()
        self.assertEqual("block", self.wiki.preflight("E_CONFIG", self.context())["decision"])
        (self.base / "ready.txt").write_text("ready")
        self.assertEqual("pass", self.wiki.preflight("E_CONFIG", self.context())["decision"])

    def test_preflight_rechecks_knowledge_changed_after_search(self):
        item = self.verified()
        search = self.wiki.search
        def update_during_preflight(*args, **kwargs):
            result = search(*args, **kwargs)
            self.edit_meta(item, status="needs-verification", confidence="observed")
            return result
        with patch.object(self.wiki, "search", side_effect=update_during_preflight):
            result = self.wiki.preflight("E_CONFIG", self.context())
        self.assertEqual("unknown", result["decision"])
        self.assertFalse(result["hits"][0]["actionable"])

    def test_preflight_rechecks_source_changed_after_search(self):
        self.verified()
        search = self.wiki.search
        def change_source(*args, **kwargs):
            result = search(*args, **kwargs)
            self.write("raw/passed.txt", "Evidence changed during preflight")
            return result
        with patch.object(self.wiki, "search", side_effect=change_source):
            self.assertEqual("unknown", self.wiki.preflight("E_CONFIG", self.context())["decision"])

    def test_preflight_many_hits_do_not_multiply_full_library_reads(self):
        item = self.verified()
        original = self.wiki.find(item["id"])
        for number in range(12):
            meta = {**original["metadata"], "id": f"{number:032x}"}
            self.write(f"wiki/cards/{meta['id']}.md", serialize(meta, original["body"]))
        with patch.object(self.wiki, "documents", wraps=self.wiki.documents) as reads:
            result = self.wiki.preflight("E_CONFIG", self.context())
        self.assertEqual("block", result["decision"])
        self.assertEqual(5, len(result["hits"]))
        self.assertEqual(13, result["matched_count"])
        self.assertEqual(13, len(result["checks"]))
        self.assertLessEqual(reads.call_count, 2)

    def test_preflight_keeps_late_rules_but_bounds_display(self):
        item = self.verified(rules=[])
        original = self.wiki.find(item["id"])
        for number in range(55):
            meta = {**original["metadata"], "id": f"late-{number:03d}"}
            if number == 54:
                meta["rules"] = [{"condition": "file_exists", "path": "missing.txt", "on_failure": "block"}]
            self.write(f"wiki/cards/{meta['id']}.md", serialize(meta, original["body"]))
        result = self.wiki.preflight("E_CONFIG", self.context())
        self.assertEqual("block", result["decision"])
        self.assertTrue(any(c["id"] == "late-054" and c["result"] == "block" for c in result["checks"]))
        self.assertLessEqual(len(result["hits"]), 5)
        self.assertLessEqual(result["summary_characters"], 6000)

    def test_preflight_excludes_other_operations_before_trust_checks(self):
        relevant = self.verified()
        unrelated = self.verified(operation="diagnose", error="E_CONFIG unrelated operation")
        self.edit_meta(unrelated, status="needs-verification")
        (self.base / "ready.txt").write_text("ready")
        result = self.wiki.preflight("E_CONFIG", self.context())
        self.assertEqual("pass", result["decision"])
        self.assertEqual([relevant["id"]], [hit["id"] for hit in result["hits"]])

    def resolution_capture(self):
        evidence = self.write("raw/capture-evidence.txt", "Actual isolated check exited 0")
        return {"observation": {"title": "Repair captured after validation", "operation": "deploy",
                                "error": "E_CONFIG missing configuration", "scope": {"os": "linux"}},
                "verification": {"outcome": "passed", "method": "isolated check", "scope": {"os": "linux"}},
                "sources": [{"type": "file", "path": "raw/capture-evidence.txt", "sha256": digest(evidence.read_bytes())}],
                "resolution": "Preparing the configuration made the actual check succeed."}

    def test_resolve_captures_atomically_and_replays_without_duplication(self):
        payload = self.resolution_capture()
        with patch.object(self.wiki.store, "commit", wraps=self.wiki.store.commit) as commits:
            item = self.wiki.resolve(None, payload, "capture-once")
        self.assertEqual(1, commits.call_count)
        self.assertTrue(self.wiki.resolve(None, payload, "capture-once")["replayed"])
        doc = self.wiki.find(item["id"])
        self.assertEqual("active", doc["metadata"]["status"])
        self.assertEqual("verified", doc["metadata"]["confidence"])
        self.assertEqual(1, doc["metadata"]["occurrences"])
        self.assertEqual(1, len(self.wiki.documents()))
        self.assertTrue(self.wiki.check()["healthy"])
        self.assertTrue(doc["metadata"]["history_sources"])
        with self.assertRaises(WikiError):
            self.wiki.resolve(None, {**payload, "resolution": "Different result"}, "capture-once")

    def test_resolve_invalid_capture_leaves_no_candidate_or_event(self):
        payload = self.resolution_capture()
        payload["verification"]["scope"] = {"os": "windows"}
        before = self.wiki.snapshot()
        with self.assertRaises(WikiError):
            self.wiki.resolve(None, payload, "invalid-capture")
        self.assertEqual(before, self.wiki.snapshot())
        self.assertFalse((self.root / "raw/memory/invalid-capture.json").exists())
        payload = self.resolution_capture()
        self.write("raw/capture-evidence.txt", "Changed evidence")
        with self.assertRaises(WikiError):
            self.wiki.resolve(None, payload, "invalid-capture")
        self.assertEqual(before, self.wiki.snapshot())

    def test_resolve_capture_reuses_failure_fingerprint_with_new_evidence(self):
        original = self.record()
        item = self.wiki.resolve(None, self.resolution_capture(), "capture-existing")
        self.assertEqual(original["id"], item["id"])
        self.assertEqual(2, self.wiki.find(item["id"])["metadata"]["occurrences"])
        self.assertTrue(self.wiki.check()["healthy"])

    def test_cli_resolve_accepts_observation_without_id(self):
        result = subprocess.run([sys.executable, str(REPO / "scripts/wiki.py"), "resolve", str(self.root),
                                 "--input", "-", "--format", "json"], input=json_text(self.resolution_capture()),
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertEqual("verified", self.wiki.find(json.loads(result.stdout)["id"])["metadata"]["confidence"])

    def test_directory_does_not_satisfy_file_prerequisite(self):
        self.verified()
        (self.base / "ready.txt").mkdir()
        self.assertEqual("block", self.wiki.preflight("E_CONFIG", self.context())["decision"])

    def test_different_or_unknown_environment_does_not_block(self):
        self.verified()
        self.assertEqual("unknown", self.wiki.preflight("E_CONFIG", self.context(environment={"os": "windows"}))["decision"])
        self.assertEqual("unknown", self.wiki.preflight("E_CONFIG", self.context(environment={}))["decision"])
        self.assertEqual("unknown", self.wiki.preflight("E_CONFIG", self.context(operation="other"))["decision"])

    def test_sources_changed_or_review_due_do_not_block(self):
        item = self.verified()
        self.write("raw/passed.txt", "Changed evidence")
        self.assertEqual("unknown", self.wiki.preflight("E_CONFIG", self.context())["decision"])
        self.edit_meta(item, review_after="2020-01-01")
        self.assertTrue(self.wiki.search("配置", self.context())["hits"][0]["needs_review"])

    def test_volatile_requires_live_verification(self):
        item = self.verified(volatile=True)
        self.assertEqual("unknown", self.wiki.preflight("E_CONFIG", self.context())["decision"])
        self.assertEqual("block", self.wiki.preflight("E_CONFIG", self.context(live_verified_ids=[item["id"]]))["decision"])

    def test_conflict_prevents_action_and_promotion(self):
        item = self.verified()
        other = self.record(error="Another failure")
        self.edit_meta(item, conflicts=[other["id"]])
        self.assertFalse(self.wiki.search("E_CONFIG", self.context())["hits"][0]["actionable"])
        with self.assertRaises(WikiError):
            self.wiki.promote(item["id"])

    def test_one_sided_conflict_invalidates_both_claims(self):
        first = self.verified(error="E_CONFIG first")
        second = self.verified(error="E_CONFIG second")
        self.edit_meta(first, conflicts=[second["id"]])
        self.assertTrue(all(not hit["actionable"] for hit in self.wiki.search("E_CONFIG", self.context())["hits"]))
        with self.assertRaises(WikiError):
            self.wiki.promote(second["id"])

    def test_resolve_requires_new_evidence_and_exact_scope(self):
        item = self.record()
        with self.assertRaises(WikiError):
            self.wiki.resolve(item["id"], {"verification": {"outcome": "passed", "method": "trust me"}})

    def test_promotion_preserves_evidence_and_redirects(self):
        item = self.verified()
        promoted = self.wiki.promote(item["id"])
        self.assertEqual("superseded", self.wiki.find(item["id"])["metadata"]["status"])
        self.assertEqual(promoted["id"], self.wiki.search("E_CONFIG", self.context())["hits"][0]["id"])
        self.assertTrue(self.wiki.check()["healthy"])

    def test_replacement_cycles(self):
        item = self.verified()
        self.edit_meta(item, status="superseded", superseded_by=item["id"])
        self.assertFalse(self.wiki.check()["healthy"])

    def test_scope_separates_same_symptom(self):
        first = self.record()
        second = self.record(scope={"os": "windows"})
        self.assertNotEqual(first["id"], second["id"])
        hits = self.wiki.search("E_CONFIG", self.context())["hits"]
        self.assertEqual([first["id"]], [h["id"] for h in hits])
        self.assertEqual(first["id"], second["related_suggestions"][0]["id"])

    def test_project_isolation(self):
        item = self.verified()
        self.edit_meta(item, project_id="another-project")
        self.assertEqual([], self.wiki.search("E_CONFIG", self.context())["hits"])
        with self.assertRaises(WikiError):
            self.wiki.promote(item["id"])

    def test_summary_budget(self):
        for i in range(8):
            self.record(error=f"E_CONFIG {i}", symptoms="配置" * 2000)
        result = self.wiki.search("配置", self.context(), budget=700)
        self.assertEqual(5, len(result["hits"]))
        self.assertLessEqual(sum(len(h["summary"]) for h in result["hits"]), 700)

    def test_retrieval_returns_redacted_evidence_within_shared_budget(self):
        item = self.verified()
        source = "Actual command exited 0. password=" + "simulated-value-" * 30 + "\n"
        evidence = self.write("raw/passed.txt", source)
        doc = self.wiki.find(item["id"])
        doc["metadata"]["sources"][0]["sha256"] = digest(evidence.read_bytes())
        self.write(doc["path"], serialize(doc["metadata"], doc["body"]))
        result = self.wiki.search("E_CONFIG", self.context(), budget=260)
        preview = result["hits"][0]["source_previews"][0]
        self.assertIn("Actual command exited 0", preview["text"])
        self.assertNotIn("simulated-value", preview["text"])
        self.assertEqual("untrusted_evidence", preview["content_role"])
        total = sum(len(h["summary"]) + sum(len(p["text"]) for p in h["source_previews"]) for h in result["hits"])
        self.assertEqual(total, result["summary_characters"])
        self.assertLessEqual(total, 260)

    def test_changed_source_is_not_presented_as_current_evidence(self):
        self.verified()
        self.write("raw/passed.txt", "Unverified replacement content")
        result = self.wiki.preflight("E_CONFIG", self.context())
        self.assertEqual("unknown", result["decision"])
        self.assertFalse(result["hits"][0]["actionable"])
        self.assertEqual([], result["hits"][0]["source_previews"])

    def test_malformed_source_remains_diagnostic_during_retrieval(self):
        item = self.verified()
        self.edit_meta(item, sources=[42])
        result = self.wiki.preflight("E_CONFIG", self.context())
        self.assertEqual("unknown", result["decision"])
        self.assertFalse(result["hits"][0]["actionable"])
        self.assertEqual([], result["hits"][0]["source_previews"])

    def test_paths_and_arbitrary_conditions_rejected(self):
        for rule in ({"condition": "shell", "command": "anything"},
                     {"condition": "file_exists", "path": "../../outside"}):
            with self.subTest(rule=rule), self.assertRaises(WikiError):
                self.record(rules=[rule])

    def test_binding_preserves_user_instructions_and_repeats(self):
        host_file = self.base / "AGENTS.md"
        host_file.write_text("# Existing instructions\nKeep this.\n", encoding="utf-8")
        self.wiki.bind()
        first = host_file.read_text(encoding="utf-8")
        self.wiki.bind()
        self.assertEqual(first, host_file.read_text(encoding="utf-8"))
        self.assertIn("Keep this.", first)
        self.assertIn("schema/.state/", (self.base / ".gitignore").read_text())

    def test_stale_snapshot_and_lock_prevent_lost_updates(self):
        path = self.write("wiki/log.md", "before")
        expected = version("before")
        path.write_text("another writer")
        with self.assertRaises(WikiError):
            self.wiki.store.commit({"wiki/log.md": "after"}, {"wiki/log.md": expected})
        with self.wiki.store.lock():
            with self.assertRaises(WikiError):
                self.wiki.store.commit({}, {})

    def test_transaction_resume_and_rollback(self):
        self.write("raw/a.txt", "before")
        with self.assertRaises(WikiError):
            self.wiki.store.commit({"raw/a.txt": "after", "raw/b.txt": "new"}, {"raw/a.txt": version("before"), "raw/b.txt": None}, "interrupted", fail_after=1)
        with self.assertRaises(WikiError):
            self.wiki.search("anything")
        self.wiki.store.recover()
        self.assertEqual("new", (self.root / "raw/b.txt").read_text())
        self.wiki.store.recover("interrupted", rollback=True)
        self.assertEqual("before", (self.root / "raw/a.txt").read_text())
        self.assertFalse((self.root / "raw/b.txt").exists())

    def test_recovery_does_not_clobber_later_edit(self):
        with self.assertRaises(WikiError):
            self.wiki.store.commit({"raw/a.txt": "after", "raw/b.txt": "new"}, {"raw/a.txt": None, "raw/b.txt": None}, fail_after=1)
        self.write("raw/a.txt", "manual repair")
        with self.assertRaises(WikiError):
            self.wiki.store.recover()

    def test_migration_preview_backup_and_rollback(self):
        original = self.legacy()
        preview = self.wiki.migrate()
        self.assertFalse(preview["applied"])
        self.assertEqual(original, (self.root / "wiki/cards/legacy.md").read_text(encoding="utf-8"))
        migrated = self.wiki.migrate(apply=True)
        self.assertTrue(migrated["applied"])
        doc = self.wiki.documents()[0]
        self.assertFalse(doc["legacy"])
        self.assertEqual("needs-verification", doc["metadata"]["status"])
        self.wiki.store.recover(migrated["operation_id"], rollback=True)
        self.assertEqual(original, (self.root / "wiki/cards/legacy.md").read_text(encoding="utf-8"))

    def test_invalid_legacy_is_preserved(self):
        text = self.legacy(Source="TODO")
        result = self.wiki.migrate(apply=True)
        self.assertTrue(result["skipped"])
        self.assertEqual(text, (self.root / "wiki/cards/legacy.md").read_text(encoding="utf-8"))

    def test_migration_preserves_crlf_bytes(self):
        text = self.legacy()
        path = self.root / "wiki/cards/legacy.md"
        original = text.replace("\n", "\r\n").encode("utf-8")
        path.write_bytes(original)
        migrated = self.wiki.migrate(apply=True)
        backup = self.root / "raw/migrations" / migrated["operation_id"] / "wiki/cards/legacy.md"
        self.assertEqual(original, backup.read_bytes())
        self.wiki.store.recover(migrated["operation_id"], rollback=True)
        self.assertEqual(original, path.read_bytes())

    def test_migration_backup_precedes_rewrite(self):
        original = self.legacy()
        commit = self.wiki.store.commit
        def interrupt_after_backup(*args, **kwargs):
            return commit(*args, **kwargs, fail_after=1)
        with patch.object(self.wiki.store, "commit", side_effect=interrupt_after_backup), self.assertRaises(WikiError):
            self.wiki.migrate(apply=True)
        self.assertEqual(original, (self.root / "wiki/cards/legacy.md").read_text(encoding="utf-8"))
        self.assertEqual(1, len(list((self.root / "raw/migrations").rglob("legacy.md"))))
        self.wiki.store.recover(rollback=True)

    def test_reindex_preserves_manual_text_and_does_not_mask_changes(self):
        item = self.verified()
        index = self.root / "wiki/index.md"
        index.write_text("# Human introduction\n", encoding="utf-8")
        self.wiki.reindex()
        self.assertIn("Human introduction", index.read_text(encoding="utf-8"))
        self.write("raw/passed.txt", "Evidence changed after indexing")
        self.assertFalse(self.wiki.search("配置", self.context())["hits"][0]["actionable"])

    def test_shared_requires_public_evidence_and_keeps_scope(self):
        item = self.verified()
        with self.assertRaises(WikiError):
            self.wiki.promote(item["id"], "shared", {})
        payload = {"title": "Configuration prerequisite", "body": "# Configuration\n\nPrepare required configuration before deployment.",
                   "generalization": {"basis": "normative-source", "explanation": "The public specification states the prerequisite."},
                   "sources": [{"type": "url", "url": "https://example.com/specification", "checked_at": today()}]}
        result = self.wiki.promote(item["id"], "shared", payload)
        shared = Wiki(self.base / "shared")
        self.assertEqual({"os": "linux"}, shared.find(result["id"])["metadata"]["scope"])
        self.assertTrue(shared.check()["healthy"])

    def test_cli_json_and_legacy_wrappers(self):
        for entry, args in (("wiki.py", ["check"]), ("check_llm_wiki.py", [])):
            result = subprocess.run([sys.executable, str(REPO / "scripts" / entry), *args, str(self.root), "--format", "json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(2, json.loads(result.stdout)["schema_version"])
            self.assertTrue({"diagnostics", "knowledge_ids", "evidence"}.issubset(json.loads(result.stdout)))

    def test_cli_uses_utf8_even_with_an_ascii_pipe_default(self):
        payload = {"title": "中文路径与字符 🧪", "error": "E_UTF8"}
        env = {**os.environ, "PYTHONIOENCODING": "ascii", "PYTHONUTF8": "0"}
        result = subprocess.run([sys.executable, str(REPO / "scripts/wiki.py"), "record", str(self.root), "--input", "-", "--format", "json"],
                                input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(payload["title"], self.wiki.find(json.loads(result.stdout)["id"])["metadata"]["title"])

    def test_resolution_and_promotion_replay(self):
        item = self.verified()
        doc = self.wiki.find(item["id"])
        payload = {"verification": doc["metadata"]["verification"], "sources": doc["metadata"]["sources"], "resolution": "Confirmed repair"}
        self.wiki.resolve(item["id"], payload, "resolve-once")
        before = (self.root / item["path"]).read_bytes()
        self.assertTrue(self.wiki.resolve(item["id"], payload, "resolve-once")["replayed"])
        self.assertEqual(before, (self.root / item["path"]).read_bytes())
        with self.assertRaises(WikiError):
            self.wiki.resolve(item["id"], {**payload, "resolution": "Different"}, "resolve-once")
        result = self.wiki.promote(item["id"], operation_id="promote-once")
        replay = self.wiki.promote(item["id"], operation_id="promote-once")
        self.assertEqual(result["id"], replay["id"])
        self.assertTrue(replay["replayed"])

    def test_malformed_rules_are_diagnostics(self):
        for rule in ({"condition": []}, {"condition": "file_exists", "base": [], "path": "x"},
                     {"condition": "file_exists", "on_failure": {}, "path": "x"}):
            with self.subTest(rule=rule), self.assertRaises(WikiError):
                self.record(rules=[rule])
        item = self.record()
        self.edit_meta(item, superseded_by=[])
        self.assertFalse(self.wiki.check()["healthy"])

    def test_malformed_configuration_is_diagnostic(self):
        config = dict(self.wiki.config)
        for field in ("shared_root", "project_root", "project_id", "shared"):
            self.write(CONFIG, json_text({**config, field: []}))
            with self.subTest(field=field), self.assertRaises(WikiError):
                Wiki(self.root)

    def test_unscoped_rule_cannot_block(self):
        self.verified(scope={})
        self.assertEqual("unknown", self.wiki.preflight("E_CONFIG", self.context())["decision"])

    def test_recovery_rejects_internal_state_and_traversal(self):
        for path in ("schema/.state/writer.lock", "../outside.txt"):
            journal = {"operation_id": "tampered", "status": "pending", "before": {path: None}, "after": {path: "unsafe"}}
            self.write("schema/.state/transactions/tampered.json", json_text(journal))
            with self.subTest(path=path), self.assertRaises(WikiError):
                self.wiki.store.recover()

    def test_lock_blocks_a_separate_process(self):
        with self.wiki.store.lock():
            result = subprocess.run([sys.executable, str(REPO / "scripts/wiki.py"), "reindex", str(self.root), "--format", "json"],
                                    capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(2, result.returncode)
        self.assertIn("writer lock", json.loads(result.stdout)["diagnostics"][0]["message"])

    def test_shared_publication_does_not_copy_private_history(self):
        item = self.verified(title="Internal host /home/private", error="Private hostname service.internal")
        payload = {"title": "Public prerequisite", "body": "# Public procedure\n\nPrepare configuration.",
                   "generalization": {"basis": "normative-source", "explanation": "Public prerequisite specification."},
                   "sources": [{"type": "url", "url": "https://example.com/specification", "checked_at": today()}]}
        result = self.wiki.promote(item["id"], "shared", payload, "publish-once")
        shared = Wiki(self.base / "shared")
        text = shared.find(result["id"])["text"]
        self.assertNotIn("service.internal", text)
        self.assertNotIn("/home/private", text)
        self.assertTrue(self.wiki.promote(item["id"], "shared", payload, "publish-once")["replayed"])


if __name__ == "__main__":
    unittest.main()
