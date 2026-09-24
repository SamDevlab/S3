# Exact Segment Budget Readiness Matrix

Candidate: P2 `1a76e341098b54a639fec22eecea362cc243c46f`.
This matrix distinguishes technical evidence from release/promotion gates.

| Area | Status | Evidence | Blocker? | Required action / next owner |
| --- | --- | --- | --- | --- |
| Candidate provenance | PASS | P0-to-P2 delta limited to intended x86-64 backend/planner, focused test, experiment reports; manifest in review | No | Keep exact candidate hashes in any later extraction |
| E0 semantics | PASS_WITH_DOCUMENTED_SCOPE | Focused boundary, slow-path, side-effect, calls, re-entry, and failure-context tests | No for serialized scope | Preserve test mapping in the proposed ADR |
| Instruction-limit boundaries | CONDITIONAL | Domain is 1..U64_MAX; 5,000,000,000 and U64_MAX exercised; exact signed-32-bit adjacent limits not independently tested | Yes | Add tests for 0x7fffffff and 0x80000000 |
| Calls | PASS | Call barrier and loop/call differential tests | No | Keep call barrier and accounting-order gates |
| Callbacks / re-entry | PASS_WITH_DOCUMENTED_SCOPE | Synchronous callback re-entry and side-effect boundary tested | No | Preserve the synchronous-only claim |
| Concurrent FFI | CONDITIONAL | Global unsynchronized counter; no public guarantee or qualification found | Yes | Decide explicit serialized-only scope or run a separate design/qualification |
| Compatibility | PASS | No language, Assembly/IR format, ABI, calling-convention, or default changes; representative P0 byte identity | No | Retain default byte-identity corpus |
| API surface | CONDITIONAL | Mode on exported `X8664Backend`; enum not re-exported; top-level API/CLI do not select it | Yes for supported opt-in | Keep internal until API policy is deliberate |
| Default-mode strategy | CONDITIONAL | `PER_INSTRUCTION` remains default | No current behavior change | Recommend `KEEP_EXPERIMENTAL_INTERNAL` pending gates |
| Code size | CONDITIONAL | `.text` growth +39.17% RMSD, +53.35%-53.57% XSBench, +58.27%-58.54% JSMN | Yes | Product owner defines acceptable binary-size scope; no architecture search |
| Performance evidence | PASS_WITH_DOCUMENTED_SCOPE | 92.14%-104.56% excess recovery in six frozen cells; reproducibility and correctness recorded | No | Keep claims to named workloads/protocol |
| Linux x86-64 native | PASS | P2 focused native E0 and full suite evidence | No within stated target | Run native smoke in any future candidate CI |
| Other platforms | NOT_APPLICABLE to this scoped candidate | No P2 native qualification for Windows, ARM64, or macOS | Conditional if scope expands | Qualify only targets required by product policy |
| Dependency stack | CONDITIONAL | PRs #301-#309 are open Draft; #310 is stacked and has non-P2 hardening differences | Yes | Integrate parents or separately review clean P2 extraction |
| S3 CI | BLOCKED | Actions enabled; recent #310 runs fail with `steps=[]`, no logs, root cause unknown | Yes | Attribute pre-step failure and obtain one valid green run |
| Benchmark CI | BLOCKED | Actions permission `enabled=false`; no runs/checks on #24 | Yes | Restore workflow execution and capture valid results |
| Benchmark wrapper | CONDITIONAL | P2H full-suite wrapper failed after pytest; pytest exit not independently captured; distinct from P2 benchmark full-suite result | Operational debt | Repair wrapper in a separate tooling change before relying on it as a release gate |
| Documentation | CONDITIONAL | P2 report has earlier f435/4,372 entry; independent final report binds 4,373 to P2 SHA | Yes for audit clarity | Preserve reconciliation; correct through a separate docs-only update if desired |
| ADR | CONDITIONAL | Proposed ADR created, not accepted | Governance gate | Human/project review required; this document does not accept it |
| Rollback | PASS as proposal | Rebuild with `PER_INSTRUCTION`; no language/data migration; artifact must be regenerated | No | Keep P0 fallback and document rebuild/redeploy requirement |
| Regression testing | PASS as proposal | Required focused/full/native/performance tiers enumerated | No | Implement gates only in separately authorized release campaign |
| Supportability | CONDITIONAL | Moderate complexity; mode not encoded in artifact metadata | No for internal mode | Preserve mode/config in build evidence for diagnosis |
| Security/resource controls | PASS_WITH_DOCUMENTED_SCOPE | Exact precharge guard and scalar fallback; frame/bounds/register checks remain | No for serialized mode | Keep U64 and budget-boundary tests; concurrency remains separate |

## Decision

```text
TECHNICAL_CANDIDATE_READINESS=CONDITIONAL
RELEASE_GATE_READINESS=BLOCKED
PROMOTION_READINESS=READY_PENDING_MULTIPLE_BLOCKERS
S3_PRODUCTION_CHANGE_READY=NO
```
