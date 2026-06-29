# Governance

Use this guide for safety, conflicts, stale knowledge, and multi-agent collaboration.

## Safety

Never write plaintext secrets into the knowledge base:

- API keys, tokens, cookies, passwords, private keys.
- Database, SSH, cloud, or production connection strings.
- Personal information that is not needed for future work.

If source material contains sensitive data, keep only a redacted source or record where the controlled original lives.

## Conflict Handling

When two sources disagree:

1. Prefer live state or the most direct source when it is available.
2. Keep the older conclusion visible but mark it `superseded` or `deprecated`.
3. Record the conflict and resolution in `wiki/log.md`.
4. Do not create another page that repeats the same unresolved fact.

## Lifecycle Markers

Use simple status labels:

- `active`: current and usable.
- `needs-verification`: useful but not yet confirmed.
- `superseded`: replaced by a newer source.
- `deprecated`: retained for history only.

## Collaboration

Agents should not maintain private parallel facts when a shared wiki exists. They should read the schema and index first, update the canonical page for durable facts, and leave a log entry explaining what changed and why.

If the current agent cannot write files, it should output a proposed patch or file list and clearly say that the knowledge base was not updated.
