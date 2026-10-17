#!/usr/bin/env python3
"""Offline retrieval and explicit external-agent paired evaluation. Never fabricates model metrics."""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from llm_wiki.engine import Wiki
from llm_wiki.model import WikiError, digest, json_text, load_json, today, serialize, safe_path, redact, configure_utf8

REPO = Path(__file__).resolve().parents[1]


def load_cases():
    cases = load_json((REPO / "evals/scenarios.json").read_text(encoding="utf-8"))
    if len(cases) < 20 or len({c["id"] for c in cases}) != len(cases):
        raise WikiError("evaluation requires at least 20 distinct scenarios")
    return cases


def seed(root, cases):
    wiki = Wiki(root)
    wiki.init(project_key="evaluation", project_root=root.parent,
              shared_root=str(root.parent / "unused-shared"))
    ids = {}
    for case in cases:
        result = wiki.record({"title": case["title"], "operation": case["operation"], "error": case["error"],
                              "scope": case["scope"], "tags": case["tags"], "symptoms": case["error"],
                              "repair": [case["expected_resolution"]], "attempts": [{"method": case["known_bad_action"], "outcome": "failed"}]})
        evidence_path = root / "raw" / (case["id"] + ".txt")
        # Synthetic benchmark fixtures are explicitly labelled, never real-world validation.
        evidence_path.write_text("Synthetic fixture assertion: " + case["expected_resolution"], encoding="utf-8")
        wiki.resolve(result["id"], {"verification": {"outcome": "passed", "method": "synthetic fixture assertion", "scope": case["scope"]},
                                    "sources": [{"type": "file", "path": evidence_path.relative_to(root).as_posix(), "sha256": digest(evidence_path.read_bytes())}],
                                    "resolution": case["expected_resolution"]})
        ids[case["id"]] = result["id"]
    for case in cases:
        doc = wiki.find(ids[case["id"]])
        if case["id"] == "review-due":
            doc["metadata"]["review_after"] = "2020-01-01"
        elif case["id"] == "source-change":
            (root / "raw/source-change.txt").write_text("Synthetic fixture source changed", encoding="utf-8")
        elif case["id"] in {"conflict-a", "conflict-b"}:
            doc["metadata"]["conflicts"] = [ids["conflict-b" if case["id"] == "conflict-a" else "conflict-a"]]
        (root / doc["path"]).write_text(serialize(doc["metadata"], doc["body"]), encoding="utf-8", newline="\n")
    return wiki, ids


def offline(cases, workspace):
    wiki, ids = seed(workspace / "knowledge-base", cases)
    outcomes = []
    for case in cases:
        start = time.perf_counter()
        result = wiki.search(case["query"], {"operation": case["operation"], "environment": case["scope"]}, limit=3)
        found = next((h for h in result["hits"] if h["id"] == ids[case["id"]]), None)
        outcomes.append({"scenario": case["id"], "top3_hit": bool(found),
                         "applicability_correct": bool(found) and found["actionable"] == case["expected_actionable"],
                         "seconds": time.perf_counter() - start, "summary_characters": result["summary_characters"]})
    recall = sum(c["top3_hit"] for c in outcomes) / len(outcomes)
    return {"mode": "offline", "scenario_count": len(outcomes), "top3_recall": recall,
            "retrieval_gate_passed": recall >= .9 and all(c["applicability_correct"] for c in outcomes), "cases": outcomes,
            "limitations": "Synthetic lexical retrieval only; no real-agent improvement or repair-success claim."}


def read_argv(path):
    argv = load_json(path.read_text(encoding="utf-8"))
    if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) for arg in argv):
        raise WikiError("adapter file must be a JSON argv array; shell execution is not used")
    return argv


def gates(summary):
    old, new = summary["v1"], summary["v2"]
    errors = (1 - new["repeated_errors"] / old["repeated_errors"]) if old["repeated_errors"] else None
    before, after = old["median_successful_tool_calls"], new["median_successful_tool_calls"]
    calls = 1 - after / before if before and after is not None else None
    checks = {"top3_recall": new["top3_recall"] >= .9,
              "repeat_error_reduction": errors is not None and errors >= .5,
              "repair_rate_no_regression": new["success_rate"] >= old["success_rate"],
              "successful_tool_call_reduction": calls is not None and after * 5 <= before * 4}
    return {"checks": checks, "repeat_error_reduction": errors, "tool_call_reduction": calls,
            "release_gate_passed": all(checks.values()),
            "note": "A zero baseline or no successful baseline repairs cannot substantiate a reduction target."}


def export_legacy(wiki, baseline):
    """Keep the historical facts but install the baseline's own instructions."""
    for doc in wiki.documents():
        meta = doc["metadata"]
        legacy = (f"# {meta['title']}\n\n- Status: {meta['status']}\n- Confidence: {meta['confidence']}\n"
                  f"- Scope: {json.dumps(meta['scope'])}\n- Source: {meta['sources'][0]['path']}\n"
                  f"- Last verified: {meta['verified_at']}\n- Tags: {', '.join(meta['tags'])}\n\n{doc['body']}\n\n"
                  "## Historical provenance notes\n\n```json\n" + json_text(meta) + "```\n")
        (wiki.root / doc["path"]).write_text(legacy, encoding="utf-8")
    rules = baseline / "assets/templates/schema/AGENTS.md"
    if not rules.is_file():
        raise WikiError("baseline is missing its own schema rules template")
    rendered = rules.read_text(encoding="utf-8")
    for old, new in {"Project key: TODO": "Project key: " + wiki.config["project_key"],
                     "Knowledge-base root: TODO": "Knowledge-base root: " + str(wiki.root),
                     "Maintainer: TODO": "Maintainer: agents"}.items():
        rendered = rendered.replace(old, new)
    (wiki.root / "schema/AGENTS.md").write_text(rendered, encoding="utf-8")
    # This file is emitted by the v2 initializer, not by the baseline initializer.
    # Do not manufacture an extra-root failure in the v1 comparison.
    (wiki.root / ".gitignore").unlink(missing_ok=True)


def agent_runs(cases, workspace, adapter, judge, baseline, repetitions):
    if not baseline or not (baseline / "SKILL.md").is_file():
        raise WikiError("agent mode requires --baseline-skill with an exported v1 skill")
    argv, judge_argv = read_argv(adapter), read_argv(judge)
    rows = []
    models = set()
    # Alternating variant order reduces temporal bias; every call has a fresh fixture.
    for case_index, case in enumerate(cases):
        for repetition in range(repetitions):
            variants = ("v1", "v2") if (case_index + repetition) % 2 == 0 else ("v2", "v1")
            for variant in variants:
                run = workspace / f"{case['id']}-{repetition}-{variant}"
                run.mkdir()
                skill = run / "skill"
                shutil.copytree(baseline if variant == "v1" else REPO, skill,
                                ignore=shutil.ignore_patterns(".git", ".eval-runs", ".test-tmp", "__pycache__", "evals", "tests", "dist"))
                wiki, ids = seed(run / "knowledge-base", cases)
                if variant == "v1":
                    export_legacy(wiki, baseline)
                request = {"schema_version": 2, "scenario_id": case["id"], "variant": variant, "repetition": repetition,
                           "workspace": str(run), "skill_root": str(skill), "knowledge_root": str(wiki.root),
                           "prompt": "Use the supplied skill and existing project experience to diagnose this simulated problem. " + case["query"],
                           "phase": case["phase"],
                           "context": {"operation": case["operation"], "environment": case["scope"]}}
                # Gold resolutions, bad-action labels and target metrics are not sent to host or judge.
                (run / "request.json").write_text(json_text(request), encoding="utf-8")
                start = time.perf_counter()
                result = subprocess.run(argv, input=json_text(request), capture_output=True, text=True, encoding="utf-8", timeout=300, cwd=run)
                (run / "adapter-stdout.txt").write_text(redact(result.stdout), encoding="utf-8")
                (run / "adapter-stderr.txt").write_text(redact(result.stderr), encoding="utf-8")
                if result.returncode:
                    raise WikiError("external agent adapter failed; no performance claim can be computed")
                response = load_json(result.stdout)
                if not isinstance(response, dict) or not isinstance(response.get("model"), str) or not isinstance(response.get("actions"), list):
                    raise WikiError("adapter must return model and observed actions")
                if not response["model"].strip() or any(not isinstance(action, str) for action in response["actions"]):
                    raise WikiError("adapter model and normalized action names must be nonempty strings")
                trace = safe_path(run, response.get("trace_path"))
                if not trace.is_file() or digest(trace.read_bytes()) != response.get("trace_sha256"):
                    raise WikiError("adapter must preserve an authentic trace with a matching fingerprint")
                if not isinstance(response.get("permissions_fingerprint"), str) or not isinstance(response.get("retrieved_ids"), list):
                    raise WikiError("adapter must report permissions fingerprint and observed retrieval IDs")
                (run / "response.json").write_text(json_text(response), encoding="utf-8")
                for field in ("tool_calls", "input_tokens", "output_tokens"):
                    if type(response.get(field)) is not int or response[field] < 0:
                        raise WikiError("adapter must report observed nonnegative usage counters")
                models.add((response["model"], response["permissions_fingerprint"]))
                if len(models) != 1:
                    raise WikiError("paired benchmark must use one identical model and permission configuration")
                judged = subprocess.run(judge_argv, input=json_text({"workspace": str(run), "scenario_id": case["id"],
                                                "trace_path": str(trace)}), capture_output=True, text=True, encoding="utf-8", timeout=300, cwd=run)
                (run / "judge-stdout.txt").write_text(redact(judged.stdout), encoding="utf-8")
                (run / "judge-stderr.txt").write_text(redact(judged.stderr), encoding="utf-8")
                if judged.returncode:
                    raise WikiError("independent fixture judge failed")
                verdict = load_json(judged.stdout)
                if not isinstance(verdict, dict) or not isinstance(verdict.get("fixture_pass"), bool) or not verdict.get("evidence"):
                    raise WikiError("judge must provide an independently observed fixture result and evidence")
                (run / "verdict.json").write_text(json_text(verdict), encoding="utf-8")
                row = {"scenario": case["id"], "variant": variant, "repetition": repetition,
                       "correct": verdict["fixture_pass"],
                       "repeated_errors": sum(a == case["known_bad_action"] for a in response["actions"]),
                       "top3_hit": ids[case["id"]] in response.get("retrieved_ids", [])[:3],
                       "seconds": time.perf_counter() - start, **{key: response[key] for key in ("tool_calls", "input_tokens", "output_tokens", "model")}}
                rows.append(row)
                (workspace / "progress.json").write_text(json_text(rows), encoding="utf-8")
    summary = {}
    for variant in ("v1", "v2"):
        items = [r for r in rows if r["variant"] == variant]
        correct = [r for r in items if r["correct"]]
        summary[variant] = {"success_rate": len(correct) / len(items), "repeated_errors": sum(r["repeated_errors"] for r in items),
                            "median_successful_tool_calls": statistics.median([r["tool_calls"] for r in correct]) if correct else None,
                            "top3_recall": sum(r["top3_hit"] for r in items) / len(items)}
    return {"mode": "agent", "scenario_count": len(cases), "repetitions": repetitions, "summary": summary, "runs": rows, **gates(summary),
            "limitations": "Adapter must collect actual host traces. Synthetic task success is not production incident success."}


def main():
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "agent"), default="offline")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--judge", type=Path, help="Independent fixture checker argv; receives no expected answer")
    parser.add_argument("--baseline-skill", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        cases = load_cases()
        if args.mode == "agent":
            if not args.adapter or not args.judge or args.repetitions < 3:
                raise WikiError("agent evaluation requires --adapter, --judge and at least 3 repetitions")
            workspace = args.output.parent / ("agent-" + uuid.uuid4().hex)
            workspace.mkdir()
            report = agent_runs(cases, workspace, args.adapter.resolve(), args.judge.resolve(), args.baseline_skill.resolve() if args.baseline_skill else None, args.repetitions)
            report["artifacts"] = str(workspace)
        else:
            with tempfile.TemporaryDirectory(prefix="wiki-eval-", dir=args.output.parent) as name:
                report = offline(cases, Path(name))
        args.output.write_text(json_text(report), encoding="utf-8")
        print(json_text({k: v for k, v in report.items() if k not in {"cases", "runs"}}))
        return 0 if report.get("release_gate_passed", report.get("retrieval_gate_passed", False)) else 1
    except (WikiError, subprocess.TimeoutExpired, OSError, UnicodeError) as exc:
        args.output.write_text(json_text({"status": "blocked", "mode": args.mode, "artifacts": str(workspace) if "workspace" in locals() else None,
                                        "reason": str(exc) if isinstance(exc, WikiError) else "adapter timeout or filesystem/process unavailable"}), encoding="utf-8")
        print("Evaluation blocked; see report. No performance target marked passed.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
