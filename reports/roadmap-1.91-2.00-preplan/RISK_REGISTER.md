# M1.91-M2.00 Risk Register

| Risk | Impact | Mitigation | Exit evidence |
|---|---|---|---|
| async CFG state explosion | unsound or unbounded execution | bounded state budgets and verifier proofs | deterministic CFG tests |
| synchronization race | lost wake or double ownership | serialized transitions and model tests | contention/cancellation matrix |
| streaming resource leak | descriptor or memory exhaustion | byte, queue, and timeout budgets | forced-close fixtures |
| TLS policy regression | accepting untrusted peers | provider boundary and fail-closed defaults | trust/rejection matrix |
| registry confusion | wrong package or cache poisoning | origin/digest/version binding | bad-digest and conflict tests |
| trust-policy ambiguity | unauthorized package acceptance | explicit key/publisher policy records | rotation/revocation proof |
| cross-target ABI drift | native-only miscompilation | target-specific object and differential gates | native matrix |
| benchmark false attribution | optimization claim unsupported | pinned workload and independent reference | reproducible report |
| release drift | non-reproducible candidate | deterministic bundle and provenance | byte/hash equality |
| roadmap stacking | unreviewed dependency changes | one milestone and merge before next | ancestry audit |

Any unresolved high risk blocks promotion. A platform deferment is recorded as
deferred, never silently converted to PASS.
