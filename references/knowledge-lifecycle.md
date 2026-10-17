# Experience lifecycle

Failure evidence must distinguish what the program printed, what the shell returned,
and what the host tool reported. Wrappers and pipelines can replace native exit codes.
When the native status is not exposed, record the wrapper status with its origin and
leave the native status unknown. Do not upgrade an inferred value into an observation.

1. Search relevant project and applicable shared knowledge before substantial work.
2. Preflight a matched operation with explicit environment and operation identity.
3. Capture a reusable observation, correction or failure using record.
4. Test the proposed repair, preserve evidence, then resolve with the tested scope.
5. Promote a durable verified conclusion into a topic or publish generalized experience.
6. Mark stale, contradicted, superseded or deprecated knowledge so it cannot silently guide work.

## Failure lessons

Capture symptoms/error signature, operation, environment, attempted method and observed
result, root-cause evidence, unverified hypotheses, repair proposal, success criterion,
exclusions and next discriminating check. Store compact redacted evidence, not a transcript.

A fingerprint includes project identity, full scope, operation and normalized error.
Normalization removes whitespace differences, timestamps and UUIDs; it preserves error
codes, paths, versions and operation semantics. Exact matches accumulate occurrences.
Semantic similarity only influences retrieval: it never merges causes automatically.

Repeated failure after resolution makes the card need verification again. Occurrences do
not increase confidence. An unresolved failure can warn about a failed approach without
claiming a known root cause or repair.

## Verification and freshness

Candidates are observed and need verification. Resolve requires new accessible evidence,
a passed check, a method, date and exactly matching environment scope.
Resolve retains previous sources as history and uses new sources for current validity.

Code-related facts follow project_file fingerprints. Volatile live facts require a fresh
check in the current task, passed as live_verified_ids. Other knowledge may specify
review_after. Conflicts make a conclusion non-actionable until reconciled with evidence.
The caller must not assert live verification merely to silence a warning.

Promotion preserves evidence, scope and verification. The original card becomes superseded
and points at the topic. Shared publication creates a separately owned portable conclusion;
the original project card remains authoritative for that project.

## Shared promotion

Provide an explicit generalized body and public checked URL evidence, plus a basis:
normative-source or cross-environment-test. Do not copy private incident details.
Existing scope stays unchanged. To broaden it, first independently verify a new card with
that scope. Project-specific file fingerprints and knowledge-root checks cannot be shared.
Publishing to the shared library is a single transaction in that library.

## Retirement and conflicts

Retain history; link superseded knowledge to its replacement. Do not delete the old evidence.
A source change means “reverify,” not automatically “false.” Record opposing evidence before
resolving a conflict. Do not automatically change permissions or governance based on a lesson.
