# Validation record

Dates: 2026-10-16 to 2026-10-17. Baseline: `9fe36dae3bb845af0c9c84bd2ac8c25d07169cdf`.
Local execution environments: Windows (Python 3.10.11, 3.12.10 and 3.15.0) and isolated
Debian 13 x86_64 (Python 3.10.22 and 3.15.0). Codex's cross-session lifecycle passed.
The first candidate completed all 120 paired model observations, but its efficiency
target failed and its known-error reduction target was not measured correctly.
That historical result remains preserved. The optimized candidate below completes all
120 valid observations; functionality passes, but two effect targets remain unmet.
Release effect targets have not all passed. On 2026-10-17, after reviewing the remaining
limitations, the user explicitly authorized committing and pushing this v2 test candidate.
That authorization does not change the recorded measurements or imply a stable release.

## Optimization verification (2026-10-17)

The optimized runtime passed 72 full regression tests on Windows Python 3.10.11,
3.12.14 and 3.15.0, and on isolated Linux Python 3.10.22 and 3.15.0. Three additional
evaluation-boundary tests passed on all five environments after fixing a floating-point
comparison that incorrectly rejected exactly 20% improvement. Combined discovery is 75;
the unchanged 72 tests were not redundantly rerun after that evaluation-only patch.
The final scripts/tests digest is
`390f13fe26d46e5a1d9262cde885c69a74732ee8ce5dcfcbbd16f490c0b5ef67`.

The 72-test runtime snapshot also passed all 20 offline scenarios, package validation
and extracted CLI checks on Windows and both Linux versions. All owned offline VMs
shut down normally. The [structured deterministic record](../evals/results/optimized-validation.json)
keeps the full-run and incremental-test scopes separate.

Changes reduce duplicate work by capturing an already verified repair in one transaction,
returning bounded evidence previews with retrieval results, excluding known unrelated
operations before preflight trust checks, and evaluating every applicable rule while
displaying only five summaries. Redaction, source revalidation and the 6,000-character
shared summary budget remain enforced.

The action fixture now exposes actual operations with host-owned state and private
classification. Eighteen offline harness tests cover all 20 legal repairs and all 20
bad-action mappings; two final targeted tests cover malformed requests and absent prior
evidence. Diagnostic failures, descriptions of actions and unrelated state changes do not
count as executing historical bad methods. Rejected attempts are reported separately.

A response-open PermissionError was reproduced during Windows atomic replacement,
after the writer had closed its stream. The exact deeper OS/filter cause and the cause
of the original two errors remain unproven. The new client retries only a bounded response
read, checking identity and content metadata and retaining every error. It never resubmits
an operation. Real exclusive-lock tests verify both recovery and persistent failure;
200 final stress calls produced 200 corresponding host events without diagnostic failure.
Native exit 2 remains unknown even if the host has written a successful response.

## Optimized model comparison (current)

The [action-based report](../evals/results/agent-codex-actions-windows.json) records 20
scenarios, three repetitions and two variants: 120 valid measured sessions plus 18
valid learning sessions. Both variants used gpt-6-astra and Codex 0.163.0-alpha.10.2
with the same permissions and fresh processes. Fixtures expose actual simulated actions;
classification and expected repairs remain outside model workspaces. These results do
not establish effectiveness on production incidents or independently attest the provider.

| Measurement | v1 | v2 | Acceptance |
| --- | --- | --- | --- |
| Independently verified repairs | 60/60 | 60/60 | No regression passed |
| Relevant experience among first three reads/hits | 60/60 | 60/60 | At least 90% passed |
| Complete actual-action measurements | 60/60 | 60/60 | Measurement complete |
| Historical bad methods executed or attempted | 0 | 0 | Zero baseline cannot prove 50% reduction |
| Median tool calls for successful repairs | 10 | 9 | 10% reduction; required 20% not met |
| Median elapsed time | 92.99 s | 72.53 s | Recorded separately from tool-call gate |
| Input context usage | 17,218,837 | 14,595,465 | Includes repeated input/cached context |
| Output context usage | 149,040 | 119,961 | Recorded separately from tool-call gate |

All 120 independent final probes completed with native exit 0 and a matching host
response. Three original provider-capacity interruptions are retained: two measured
sessions and one learning session. Each affected slot received one fresh recovery with
identical frozen inputs; the interrupted learning session's recurrence was rebuilt too.
Completed valid outcomes were never retried. Original interruptions are not clean passes.

The frozen automatic recognizer missed two actual preflight invocations written with
PowerShell Join-Path parentheses. A uniform audit of unchanged output recovered their
true rank. Two other sessions printed and saved projections of four action responses;
an independent reviewer bound every invocation and retained field to unique host events.
The postprocessor rechecks trace/ledger/artifact hashes, action IDs, parameters, native
results, retained state fields and ordering. It rejects missing or changed bindings.
Original automatic false/unknown values remain alongside the audited measurements.

All 18 valid learning records passed independent blind review against actual failures,
repairs, source bytes and scope. A minimal summary can establish a verified repair when
its observations bind uniquely to real operations; retaining the final validation's
internal request ID is not itself a knowledge requirement. The original interrupted
learning attempt remains needs_review and is excluded from the 18 successful records.

The malicious-source audit covers 14 preserved traces (including the original interruption
and two recovery traces), 150 actual tool invocations and 71 simulated operations. No
recorded call expanded permissions or read private credentials. The scope is recorded
tool invocations, not unrecorded system calls. All 36 cited learning-source fingerprints
and all reviewed learning-trace fingerprints match the preserved bytes.

The product/runtime files were frozen before the model cohort. Final edits only add
reports and clarify documentation; the scripts/tests digest above is unchanged. The
original tool-call and repeat-error percentage targets remain unmet. No further cohort
is launched to retry completed valid outcomes or manufacture a positive baseline.

## First-candidate checks (historical)

- Standard-library regression suite: 63 tests passed on each of Windows Python 3.10.11,
  3.12.10 and 3.15.0; covers document contracts, all 18 original audit
  probes, Chinese/English retrieval, applicability, preflight, failure deduplication,
  redaction, one-sided conflicts, project isolation and shared-publication boundaries.
- Preflight regression checks cover knowledge/evidence changes after retrieval and prevent
  one full-library scan per hit. The evaluation setup also checks project-root binding and
  the baseline's own rendered rules without changing historical trust states.
- Linux final snapshot: 63 tests passed on Python 3.10.22 (34.731 seconds) and 3.15.0
  (27.794 seconds). Both also passed package validation, all 20 offline scenarios and
  archive extraction/entrypoint checks. The QEMU guest had no network adapter, used an
  isolated disk overlay and shut down normally; no system installation was required.
  The scripts/tests tree digest was
  `5d297b6e9566c59fb12c0a9273673152e19fc24807998952ea52899d6f0d3451`.
- Storage coverage includes a separate-process lock contender, stale write fingerprints,
  operation replay, interrupted updates, resume, rollback, tampered recovery paths and
  exact Windows CRLF migration round trips.
- Package validation checks required files, Python compilation, skill metadata,
  documentation links and extension-independent sensitive-content scanning.
- The deterministic skill ZIP was built and extracted successfully; the extracted
  package passed validation and its CLI version entrypoint ran successfully.
- Twenty offline synthetic scenarios: top-three recall 20/20; all expected applicability
  decisions passed. This is not evidence of real-model repair or efficiency improvements.
- Independent forward test used the public CLI in isolated directories: 39 initial
  CLI/fixture invocations exercised onboarding, verified repair, fresh-process retrieval,
  preflight pass/block/unknown, topic promotion and recurrence. A separate recheck confirmed
  byte-identical CRLF backup/rollback, executable rollback_argv, the documented v1 example,
  and verified conclusions leading the retrieval summary.

Commands to reproduce:

```sh
python scripts/validate_skill.py . --format json
python -m unittest discover -s tests -v
python scripts/evaluate.py --mode offline --output .eval-runs/offline.json
git diff --check
```

The CI configuration declares Windows/Linux × Python 3.10/3.15. Local Windows tests also
exercise official portable Python 3.10.11 and 3.15.0 distributions without changing the
machine's Python installation. Their downloaded hashes matched Python.org's release pages.
Python 3.15 is the current
stable feature release ([official release](https://www.python.org/downloads/release/python-3150/)). The matrix has not been
executed on GitHub as part of this local change. The equivalent commands passed on local
Windows and the isolated Linux guest; hosted CI remains a post-push check before release.

## Original audit regression mapping

| Original probe | Regression coverage |
| --- | --- |
| baseline_valid_card | valid_legacy_card_remains_readable_but_untrusted |
| reinitialize_preserves_files | init_and_repeat_preserve_files |
| empty_status_and_confidence | empty_legacy_status |
| missing_source_file | missing_legacy_source |
| invalid_verified_date | invalid_legacy_date |
| verified_date_TODO | todo_legacy_date |
| superseded_without_replacement | legacy_replacement_required |
| body_metadata_collision | code_block_does_not_override_metadata |
| topic_missing_provenance | topic_requires_provenance |
| markdown_broken_link | markdown_broken_link |
| ambiguous_wikilink | ambiguous_wikilink |
| broken_wikilink_control | broken_wikilink |
| secret_txt_control | secret_file_extensions, evidence.txt subcase |
| secret_dotenv | secret_file_extensions, .env subcase |
| secret_log | secret_file_extensions, session.log subcase |
| secret_jsonl | secret_file_extensions, session.jsonl subcase |
| root_readme_default_mismatch | root_readme_and_git_allowed |
| git_directory_strict_root | root_readme_and_git_allowed |

The full tests live in `tests/test_wiki.py` and `tests/test_evaluation.py`.

## Host integration status and release blockers

| Surface | Observed status |
| --- | --- |
| Generic CLI/protocol | Public CLI workflow tested in isolated fixtures |
| Codex project skill and AGENTS.md | Complete failure/capture/verify/new-process retrieval/preflight/repair lifecycle passed; explicit named loading and project AGENTS use observed; unsolicited activation is not established |
| Codex CLI explicit-read smoke | 0.162.0-alpha.17.2 passed with ordinary host runtime access: a new ephemeral read-only session read both SKILL.md and cli.md and correctly described the search command and advisory enforcement |
| Claude Code project skill and CLAUDE.md | Startup discovery/binding observed; full lifecycle unverified because the configured service was unavailable. The user removed Claude testing from this upgrade's required acceptance on 2026-10-16 |
| Other agents | Agent Skills/local CLI protocol only, no platform-specific test claim |
| Paired real-agent benchmark | All 20 × 3 × 2 observations completed; top-three recall passed, tool-call reduction failed, known-error reduction unmeasured, two independent probe anomalies retained |

The smoke attempts did not change global settings or install the skill into personal
directories. Bare mode skips CLAUDE.md discovery, so even a successful explicit-read run
would not establish automatic loading.
The first Codex attempt under the outer workspace-only sandbox failed before startup
because state_5.sqlite/arg0 and the in-process app-server were inaccessible (OS error 5).
The successful retry used normal approved host runtime access while keeping the inner
agent read-only; it did not bypass the agent's tool permissions.

Earlier bounded attempts found an inaccessible interactive Python installation and a
shell/native exit-code ambiguity. A later independent test used the approved host runtime
and verified the corrected workflow end to end. Codex 0.162.0-alpha.17.2 completed the first
process in 131.30 seconds: actual child exit 7, scoped record, real repair, child exit 0,
resolve with evidence, healthy knowledge base. It correctly distinguished shell status 1
from native status 7. After that process ended, only the synthetic prerequisite was removed.
A new non-resumed model process completed in 72.56 seconds: retrieved the same card,
checked source hashes, observed preflight block, prepared the prerequisite, observed pass,
and deployed with native exit 0. An incompatible Linux context returned no hits/unknown.
Independent disk verification found one active/verified card, unchanged skill files,
matching source hashes and real child outcomes [7, 0, 0].

Claude Code 2.1.133 was separately installed in an isolated project with managed CLAUDE.md,
scoped tool permissions and no global changes. Its startup event listed build-llm-wiki,
but one 502 and two 503 service errors occurred before any assistant or tool event; the
180-second attempt was stopped. No card or fixture run existed. Startup discovery alone
does not prove instruction use, writeback or fresh-session reuse.
One retry with the same Opus model and a normalized context suffix returned nine 503
events before its 180-second deadline. An already configured Sonnet route produced no
reply within 30 seconds; that timeout does not establish an HTTP error. A text-only probe
of the configured Haiku route returned 503 after 3.67 seconds and was stopped. All ran on
the local Windows machine using its installed CLI and configured service; no global
configuration or credentials were changed. No further Claude attempt is required for
this upgrade. These observations do not establish that the upstream vendor was at fault.

## First-candidate model comparison (historical)

The preserved report is [agent-codex-windows.json](../evals/results/agent-codex-windows.json).
It contains all 120 measured observations, trace fingerprints, telemetry, learning reviews
and explicit gate results. The configured model was gpt-6-astra for both variants, with
identical permissions and fresh processes. Provider identity was not independently attested.
These are local configuration simulators, not production incidents.

The checker and expected configurations stayed outside model workspaces; model skill
copies excluded tests and evaluation answers. The three initial-failure families used
18 additional learning processes. Each ended before a new recurrence directory was created;
only the knowledge library crossed that boundary. Models did not receive target metrics.
The runtime/tests digest matches the Windows and Linux validation above.

An independent evidence reviewer received neither expected answers nor improvement targets.
All 18 learning cards passed review against actual failures, host operation ledgers, source
bytes and tested scope. Seventeen libraries retained summaries or subsets of the original
inputs rather than a complete original-input bundle; genuine success evidence remained
available. This limits full historical re-audit and does not invalidate the supported,
scoped repair conclusions. Capturing an entire conversation is not required.

The malicious-source family received an additional review of all 12 completed learning and
recurrence traces: 148 actual tool calls. No observed call treated source instructions as
authorization or accessed unrelated private data. Trace fingerprints match the audit.
This finding covers recorded tool invocations, not unrecorded system calls.

| Measurement | v1 | v2 | Acceptance |
| --- | --- | --- | --- |
| Completed measured sessions | 60/60 | 60/60 | Complete |
| Relevant experience among first three actual reads/hits | 60/60 | 60/60 | At least 90% passed |
| Repairs with all original checks completed successfully | 59/60 | 59/60 | One additional probe error per version; no-regression remains uncertain |
| Median tool calls in those successful sessions | 10 | 14 | 40% more calls; required 20% reduction failed |
| Median elapsed time, all completed sessions | 94.24 s | 126.34 s | 34.1% higher; recorded separately from the gate |
| Observed input context usage | 14,383,861 | 19,568,806 | 36.0% higher |
| Observed output context usage | 140,674 | 194,979 | 38.6% higher |
| Repeated execution of named historical bad methods | Unmeasured | Unmeasured | Required 50% reduction unproven |

The extra independent probes exited 2 in `path-space-1-v1-measured` and
`conflict-b-1-v2-measured`. In both, immutable inputs remained intact, the final configuration
passed the independent state check, and the host ledger recorded the agent's successful
operation. The checker also wrote a successful response for the extra probe. These are
probe errors, not established model repair failures. The host harness omitted stderr for
that extra subprocess, so the precise failure cannot be recovered.

Host-only followups on unchanged configurations both exited 0. A bounded diagnostic run
made 1,408 actual client calls with up to eight concurrent checkers: all exited 0, with no
checker exceptions or diagnostics. The anomaly was not reproduced. Original observations
remain unchanged; followups do not retroactively turn them into clean original passes.
Confirmed repair rates are 59/60 for each variant, with upper bounds of 60/60. The report
conservatively leaves no-regression unproven while those bounds overlap.

The host's configuration-state proxy cannot establish execution of every named historical
method, such as credential rotation. Counts of failed fixture operations include legitimate
diagnostic reproductions and cannot substitute for repeated known-bad actions. No percentage
is claimed for this gate.

## Invalidated pilots and follow-up disposition

Earlier pilots exposed telemetry parsing, baseline export, answer-isolation and retrieval-rank
defects. One attempted full run was stopped after six observations and invalidated. Those
artifacts were preserved separately and contribute no observations to the table above.
The completed comparison used corrected baseline rules, a private checker, fresh recurrence
directories and actual retrieval order. It retained the later probe errors described above.

The subsequent work described above completed this original follow-up list:

1. Measure historical methods from actual tool invocations in fixtures that expose those
   operations; audit the mapping before running models. Preserve zero-baseline outcomes.
2. Reduce the extra workflow cost through concrete CLI/workflow changes, then freeze a new
   candidate. More prompt text or a changed denominator cannot establish an improvement.
3. Preserve stdout, stderr, native exit and checker diagnostics for every independent probe;
   keep infrastructure errors separate from failed repairs.
4. Repeat the fixed 20 × 3 paired comparison with the same model and permissions. Preserve
   this failed candidate's results and require the original 90%/50%/20% gates.

That follow-up established complete action measurement and passing repairs, but did not
meet the two percentage targets. The user subsequently authorized a push with these
limitations preserved. This remains a v2 test candidate, without a claim that all effect
targets have passed.
Claude remains unverified and is no longer a required host test for this upgrade.
