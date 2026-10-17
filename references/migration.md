# Compatibility, explicit migration and rollback

V1 documents remain readable. Only the initial metadata list after the title is parsed;
body/code examples cannot override it. Legacy conclusions are always candidates in retrieval.
Malformed or incomplete metadata is reported, never invented.

1. Run check and doctor; inspect unresolved sources and conflicts.
2. Run migrate without --apply to preview conversions and skipped documents.
3. Run migrate --apply only when migration has been explicitly requested.
4. Valid convertible pages receive v2 identities and needs-verification/observed status.
   Old metadata remains available, including its free-text scope; it is not guessed into a
   machine scope. Retired legacy relations and incomplete pages remain unchanged.
5. Backups are preserved under raw/migrations/<operation-id>/ with original relative paths.
6. Reverify evidence and map environment scope before marking migrated knowledge verified.

Use recover <root> --operation-id <migration-id> --rollback to undo a migration.
Rollback restores original UTF-8 bytes and removes files created by that transaction,
unless later edits conflict. Recovery never destroys such later edits.
The returned migration result includes rollback_argv with the complete rollback command.

Old init/check entrypoints remain available. Strict root validation is now consistent with
init; use --allow-extra-root explicitly where needed. --force remains accepted but preserves
existing knowledge instead of replacing accumulated logs or rules.

A Python-less agent can read the knowledge manually, but cannot claim that CLI validation,
write locking, migration backup or preflight enforcement ran.


## Minimal v1 card accepted for migration

```markdown
# Deployment prerequisite

- Status: active
- Confidence: verified
- Scope: Linux deployment fixture
- Source: raw/deployment-check.txt
- Last verified: 2026-10-16
- Tags: deployment

## Claim

Prepare the configuration before deployment.
```

The referenced file must exist. A historical date and label do not make the converted
card trusted: the conversion still requires fresh verification. Backups and rollback
preserve UTF-8 bytes, including CRLF. The result provides rollback_argv with the exact
entrypoint and knowledge-root arguments.
