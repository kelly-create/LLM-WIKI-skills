# Capture after a verified repair

Use `record` while a useful failure remains unresolved. If the real repair has already
passed its check, capture it with one `resolve` call. Both paths use the same evidence,
scope, redaction, failure-fingerprint and transaction checks.

Write a minimal redacted result under `raw/` and calculate its SHA-256. Preserve the actual
failure, relevant observations and successful check; mark unknown facts rather than inventing
them. For an existing card with new verification, supply `--id` and omit `observation`.
For a newly captured repair, omit `--id` and provide:

```json
{
  "observation": {
    "title": "Configuration prerequisite for deployment",
    "operation": "deploy",
    "error": "E_CONFIG missing configuration",
    "scope": {"os": "linux"},
    "symptoms": "Observed deployment failure before configuration was prepared",
    "attempts": [{"method": "deploy", "outcome": "E_CONFIG"}],
    "root_cause": "The prerequisite configuration was missing",
    "repair": ["Prepare the configuration, then verify deployment"],
    "success_criteria": "Deployment exits successfully",
    "not_applicable": ["A different deployment contract"],
    "next_check": "Inspect whether the prerequisite exists"
  },
  "verification": {
    "outcome": "passed",
    "method": "Executed the actual deployment check",
    "scope": {"os": "linux"}
  },
  "sources": [{"type": "file", "path": "raw/deployment-check.json", "sha256": "<SHA-256 of actual evidence bytes>"}],
  "resolution": "Preparing the configuration made the deployment check succeed."
}
```

```sh
python <absolute-skill-dir>/scripts/wiki.py resolve <knowledge-root> --input repair.json --operation-id <stable-operation-id> --format json
python <absolute-skill-dir>/scripts/wiki.py check <knowledge-root> --format json
```

The observation is retained in `raw/memory/` and the verified conclusion retains its source
chain. A matching failure reuses the existing card. Invalid evidence or scope rejects the
entire capture before writing a candidate. Replaying the same operation ID does not add an
occurrence; different input with the same ID is rejected. This does not execute a verification
on the agent's behalf: the evidence must come from a check already performed.
