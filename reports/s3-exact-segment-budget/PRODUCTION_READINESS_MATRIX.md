# Exact Segment Budget Readiness Matrix

Candidate: P2 `1a76e341098b54a639fec22eecea362cc243c46f`.
This matrix distinguishes technical evidence from release/promotion gates.
Open-blocker counting groups the S3 and S3-Benchmarks workflow issues as one
CI blocker; the limit-edge coverage row is closed and is not counted.

| Area | Status | Evidence | Blocker? | Required action / next owner |
| --- | --- | --- | --- | --- |
| Candidate provenance | PASS | P0-to-P2 delta limited to intended x86-64 backend/planner, focused test, experiment reports; manifest in review | No | Keep exact candidate hashes in any later extraction |
| E0 semantics | PASS_WITH_DOCUMENTED_SCOPE | Focused boundary, slow-path, side-effect, calls, re-entry, and failure-context tests | No for serialized scope | Preserve test mapping in the proposed ADR |
| Instruction-limit boundaries | PASS | Both modes build/link/execute at six limits including exact signed-32-bit neighbors; P0/P2 results match; P2 precharge checks `L-W` | No | Retain the boundary matrix and small-budget E0 fallback gates |
| Calls | PASS | Call barrier and loop/call differential tests | No | Keep call barrier and accounting-order gates |
| Callbacks / re-entry | PASS_WITH_DOCUMENTED_SCOPE | Synchronous callback re-entry and side-effect boundary tested | No | Preserve the synchronous-only claim |
| Concurrent FFI | PASS_WITH_DOCUMENTED_SCOPE | Human-approved Path A: serialized calls and qualified synchronous callback re-entry are supported; concurrent entry into the same loaded artifact is not supported or qualified | No; decision accepted | Preserve the contract; future same-artifact concurrency requires a separate execution-context, budget, frame-accounting, and synchronization contract |
| Compatibility | PASS | No language, Assembly/IR format, ABI, calling-convention, or default changes; representative P0 byte identity | No | Retain default byte-identity corpus |
| API surface | CONDITIONAL | Mode on exported `X8664Backend`; enum not re-exported; top-level API/CLI do not select it | No while kept experimental/internal | Revisit only if a supported public opt-in is proposed |
| Default-mode strategy | CONDITIONAL | `PER_INSTRUCTION` remains default | No current behavior change | Recommend `KEEP_EXPERIMENTAL_INTERNAL` pending gates |
| Code size | CONDITIONAL | `.text` growth +39.17% RMSD, +53.35%-53.57% XSBench, +58.27%-58.54% JSMN | Yes | Product owner defines acceptable binary-size scope; no architecture search |
| Performance evidence | PASS_WITH_DOCUMENTED_SCOPE | 92.14%-104.56% excess recovery in six frozen cells; reproducibility and correctness recorded | No | Keep claims to named workloads/protocol |
| Linux x86-64 native | PASS | Focused native gate: 75 passed; valid full suite: 4,390 passed, 1 skipped, 572 subtests passed, exit 0 at c07b2c48 | No within stated target | Run native smoke in any future candidate CI |
| Other platforms | NOT_APPLICABLE to this scoped candidate | No P2 native qualification for Windows, ARM64, or macOS | Conditional if scope expands | Qualify only targets required by product policy |
| Dependency stack | CONDITIONAL | PRs #301-#309 are open Draft; #310 is stacked and has non-P2 hardening differences | Yes | Integrate parents or separately review clean P2 extraction |
| CI (S3 and benchmark repositories) | BLOCKED | S3 natural runs fail before steps, cause unknown; benchmark Actions permission is disabled and #24 has no runs/checks | Yes, one aggregate blocker | Diagnose S3 pre-step failure and restore benchmark workflow execution; absence of checks is not a pass |
| Benchmark wrapper | CONDITIONAL | P2H full-suite wrapper failed after pytest; pytest exit not independently captured; distinct from P2 benchmark full-suite result | Operational debt | Repair wrapper in a separate tooling change before relying on it as a release gate |
| Documentation | PASS_WITH_RECONCILIATION | P2's earlier f435/4,372 entry is distinguished from its 4,373 report entry; new c07b2c48 suite transcript is preserved and hashed in #312 | No | Keep source SHA, run, and transcript provenance distinct |
| ADR | PARTIALLY_ACCEPTED_SCOPE | The concurrency decision is accepted; the overall Exact Segment Budget ADR remains proposed and does not authorize promotion | No separate concurrency blocker | Keep overall P2 promotion gated by the remaining stack, CI, and code-size blockers |
| Rollback | PASS as proposal | Rebuild with `PER_INSTRUCTION`; no language/data migration; artifact must be regenerated | No | Keep P0 fallback and document rebuild/redeploy requirement |
| Regression testing | PASS as proposal | Required focused/full/native/performance tiers enumerated | No | Implement gates only in separately authorized release campaign |
| Supportability | CONDITIONAL | Moderate complexity; mode not encoded in artifact metadata | No for internal mode | Preserve mode/config in build evidence for diagnosis |
| Security/resource controls | PASS_WITH_DOCUMENTED_SCOPE | Exact precharge guard and scalar fallback; frame/bounds/register checks remain; boundary suite passes | No for serialized mode | Keep U64 and budget-boundary tests; concurrency remains separate |

## Decision

```text
TECHNICAL_CANDIDATE_READINESS=CONDITIONAL
RELEASE_GATE_READINESS=BLOCKED
PROMOTION_READINESS=READY_PENDING_MULTIPLE_BLOCKERS
SEMANTIC_READINESS=PASS
DECISION_RECOMMENDATION=PATH_A
DECISION_AUTHORITY=HUMAN_ACCEPTANCE_REQUIRED
DECISION_STATUS=ACCEPTED
ACCEPTED_CONCURRENCY_CONTRACT=SERIALIZED_SAME_ARTIFACT_ONLY
BLOCKER_CONCURRENCY=CLOSED
OPEN_BLOCKERS=3
NEXT_CRITICAL_BLOCKER=PR_STACK
NEXT_CAMPAIGN=S3_1_X_PR_STACK_INTEGRATION_CLOSURE
S3_PRODUCTION_CHANGE_READY=NO
```
