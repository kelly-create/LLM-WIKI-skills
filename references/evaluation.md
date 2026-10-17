# Evaluation protocol

## Offline checks

```sh
python scripts/validate_skill.py . --format json
python -m unittest discover -s tests -v
python scripts/evaluate.py --mode offline --output .eval-runs/offline.json
```

`evals/scenarios.json` fixes 20 cases across recurrence, initial investigation,
environment changes and similar symptoms with different causes. Queries are not copied
into the seeded page body. The offline runner creates isolated libraries, checks top-three
retrieval and checks whether stale/conflicting evidence remains non-actionable. It uses
synthetic evidence, not claims that the listed production remedies have been verified.

The CI matrix runs these commands on Windows and Linux, Python 3.10 and 3.15.
No model API, personal shared library or external service is used in ordinary CI.
The current recorded results and host limitations are in [validation.md](validation.md).

## Manual paired agent benchmark

Export v1 from commit `9fe36dae3bb845af0c9c84bd2ac8c25d07169cdf` to an isolated folder.
Provide an environment-specific host adapter and independent fixture judge, each as a
JSON argument array file. Executables and script paths should be absolute: subprocesses
run inside fresh fixture directories. No shell interpolation is used.

```sh
python scripts/evaluate.py --mode agent --baseline-skill /absolute/v1-skill --adapter adapter.json --judge judge.json --repetitions 3 --output .eval-runs/agent.json
```

For example, adapter.json contains an argv array such as
`["python", "/absolute/host_adapter.py"]`; judge.json points to a different fixture checker.
Adapters and realistic fault environments are intentionally host-owned: the repository
does not silently select models, relax permissions, create infrastructure or spend API
credits. Until an adapter and judge have been supplied and the benchmark actually run,
the real-agent release gate is incomplete. A dummy adapter is not acceptable evidence.

Each of 20 cases runs at least three times for each version (120 paired observations).
Variant order alternates, each observation gets a fresh directory, and the model identifier
and permission fingerprint must stay identical. Both versions start with the same
knowledge, represented in their respective formats. Old entries do not gain new trust
merely by conversion. The adapter must prepare a real or simulated reproducible fixture
matching the scenario, not simply ask the model to repeat a stored answer.

For initial-investigation cases, start an additional fresh learning session without the
matching card, induce the failure, verify the repair, and allow the skill to capture it.
Then end the session and run the measured recurrence in a new session with the saved
library. For environment-change and lookalike cases, preserve the distracting old
experience and configure the changed environment before the measured session.
The adapter records both session boundaries and the actual commands/outcomes in its trace.

The adapter receives one JSON object on stdin:

```json
{
  "schema_version": 2,
  "scenario_id": "config-prereq",
  "variant": "v2",
  "repetition": 0,
  "workspace": "/isolated/run",
  "skill_root": "/isolated/run/skill",
  "knowledge_root": "/isolated/run/knowledge-base",
  "prompt": "Use the supplied skill ...",
  "phase": "recurrence",
  "context": {"operation": "deploy", "environment": {"os": "linux", "service": "fixture"}}
}
```

It must emit one JSON object on stdout (send progress to stderr):

```json
{
  "model": "actual resolved model identifier",
  "permissions_fingerprint": "same-host-tool-policy-sha256",
  "actions": ["inspect_configuration", "prepare_configuration", "verify_deployment"],
  "retrieved_ids": ["actual-knowledge-id"],
  "tool_calls": 3,
  "input_tokens": 500,
  "output_tokens": 100,
  "trace_path": "trace.jsonl",
  "trace_sha256": "sha256-of-preserved-host-trace"
}
```

Actions must be normalized from actual tool invocations by the adapter, using the scenario's
action vocabulary. Retrieval IDs must come from actual reads/searches; do not accept a
model's claim that it read a card. Counters come from host telemetry. Record elapsed time
and context cost even when a run fails. Missing telemetry must fail the run, not become zero.
Audit each action mapping before model execution. A changed configuration value or a
failed diagnostic check alone does not establish execution of a named historical method.
If fixtures do not expose those operations, mark the reduction metric unmeasured.

The judge receives only workspace, scenario_id and the preserved trace_path. It receives
neither the expected answer nor improvement targets. It independently executes the
fixture's acceptance check, then emits `{"fixture_pass": true, "evidence": [...]}` with
references to actual test outputs. A model's final assertion alone cannot establish success.
The host and judge are trusted benchmark components: fingerprints protect trace identity,
not authenticity against a dishonest adapter. Review them and retain their versions.
Preserve stdout, stderr, native exit status and checker diagnostics for every subprocess
inside the judge as well as the judge itself. Transport or protocol failures remain separate
from incorrect repairs. Keep original outcomes when adding a diagnostic rerun; do not
silently replace them with successful followups.

Run folders, requests, responses, verdicts, traces and incremental progress are preserved
next to the report even on interruption. Keep these fixtures free of credentials. Never
point the benchmark at a personal library. Do not publish unreviewed host traces.

## Release gates

All four must pass:

| Metric | Target |
| --- | --- |
| Known relevant experience in top three | At least 90% |
| Repeated execution of known failed action | At least 50% reduction from v1 |
| Independently verified correct repair rate | No regression |
| Median tool calls among correctly solved tasks | At least 20% reduction |

Zero baseline errors cannot prove a 50% reduction; no successful baseline repairs cannot
establish the tool-call target. The runner leaves such targets unmet instead of inventing
a percentage. Preserve failed cases and fix retrieval, scope or verification defects.

Codex and Claude Code each require a separate installation/load test, a new-session
retrieval test and a failure-writeback test before claiming tested platform support.
Other agents currently have protocol compatibility only.
For this upgrade, the user explicitly limited required host acceptance to Codex on
2026-10-16. Claude's incomplete lifecycle does not block this upgrade, but cannot be
represented as a successful platform test.

The optimized 2026-10-17 comparison and its unmet gates are recorded in
[validation.md](validation.md) and [the action-based report](../evals/results/agent-codex-actions-windows.json).
All 120 observations have complete action measurement: both versions executed zero
known bad methods. This is a measured zero baseline, not proof of a 50% reduction.
Successful tool-call medians are 10 and 9, a 10% reduction rather than the required 20%.
The [first candidate's report](../evals/results/agent-codex-windows.json) remains unchanged.

The optimized cohort preserved three provider-capacity interruptions and made one fresh
recovery per affected slot, using identical frozen skill/model/binary/permissions. An
interrupted learning session required repeating its learning/recurrence pair. Completed,
valid outcomes were never retried. Derived scores retain original automatic measurements:
two PowerShell command spellings were missed by the retrieval parser; two subprocess
wrappers printed projections of actual events, verified against stdout, saved evidence
and host events by an independent reviewer. These corrections do not change model actions,
tool counts or the release targets. Minimal learning evidence was independently matched
to actual operations instead of requiring an incidental internal final-validation ID.
