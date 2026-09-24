# P2 Dependency Matrix

P2 base: `e07d0b5464bf472b2ca18993f3e196a234ff0fc5`. Selected head:
`1a76e341098b54a639fec22eecea362cc243c46f`. This audits implementation
dependencies, not development ancestry.

| P2 file/symbol surface | Dependency | Origin PR | Required? | Reason |
| --- | --- | --- | --- | --- |
| `backend.py`: backend mode/configuration | Existing x86-64 backend and configuration validation | pre-#301 main | Yes | Extends existing backend; no selfhost/frontend imports |
| `emitter.py`: exact-segment emission | Existing Assembly program/function/block/instruction model, layout, liveness, x86 emission | pre-#301 main | Yes | Planner consumes the pre-existing backend representation |
| `instruction_budget.py`: plan/diagnostics | Existing backend block instruction sequence | pre-#301 main | Yes | Backend-local planner; no source-frontend or selfhost protocols |
| P2 focused tests | Existing compiler pipeline and native toolchain | pre-#301 main | Yes | Fixtures use existing APIs |
| #312 boundary-test additions | P2 mode plus current compiler/native APIs | P2 + pre-#301 main | Yes as tests, after oracle decision | c07 adds limit-domain and native boundary closure only |
| RMSD performance workload | Borrowed f64 vector references and sqrt/runtime | #308/#309 | No for P2 source; yes to reproduce that workload | Workload dependency is distinct from implementation dependency |
| `NativeIndexedValue`/aggregate-reference semantics | Native indexed/aggregate substrate | #307/#308 | No | No P2 source import/reference to these symbols |
| Source frontend and native semantic protocols | #301-#306 | No | No | No P2 source or focused P2 import depends on these features |
| #311 readiness/ADR/review files | Governance/review content | #311 | No executable dependency | Accepted Path A wording can be carried in a feature contract without the review PR |
| #312 reports/evidence/archive | Research/evidence | #312 | No | Preserve as historical material; only the test delta is a candidate companion |

Conclusion: `P2_FUNCTIONALLY_REQUIRES_301_309=NO` for implementation. The
RMSD workload used by prior performance evidence does use #308/#309; the
historical workload-specific claims must not be generalized to a composition
without that workload. No benchmark was rerun.

```text
ANCESTRY_IS_FUNCTIONAL_DEPENDENCY=NO
P2_IMPLEMENTATION_CONTENT_MATCH=YES
P2_TEST_ORACLE_COMPATIBLE_WITH_CURRENT_MAIN=NOT_PROVEN
```
