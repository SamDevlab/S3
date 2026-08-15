# P9.1 bounds and validity contract attribution checkpoint

```text
CAMPAIGN_ID=P9_1_BOUNDS_VALIDITY_CONTRACT_ATTRIBUTION_V1
STATUS=COMPLETE_RESEARCH_ONLY
ORIGIN_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
RESEARCH_HEAD_START=7880ac882db0ff4271e0c32278fef536edbaf579
P9_SELECTION=NO_VALID_TARGET_YET
P9_STARTED=NO
PRODUCTION_COMPILER_CHANGED=NO
PRODUCTION_BRANCH_CREATED=NO
PRODUCTION_PR_CREATED=NO
EXTERNAL_BENCHMARK_RERUN=NO
GITHUB_ACTIONS_EXECUTED=NO
SHUTDOWN_AUTHORIZED=NO
```

P9.1 reused the frozen P9 corpus and model. The total
`MODELLED_NATIVE_DYNAMIC_COUNT` reproduced exactly: `289500` across 15
workloads, matching the previous P9 class breakdown. Focused native
correctness passed for five candidate workloads at O0/O1. No benchmark timing,
full suite or Actions run occurred.

The safety taxonomy separated bounds, initialization, register initialization,
object/reference validity, slice provenance, mutability, failure realization
and other safety. Explicit safety realization was `65224` modelled dynamic
lines (`22.529879101900%`). Bounds were `17464` (`6.032469775475%`) and memory
initialization was `6660` (`2.300518134715%`). Hot failure edges were measured
separately; cold failure setup had zero modelled dynamic weight on the
correctness inputs. P8 register initialization was not reselected.

The minimum model tried local constants, dominated `TCMP` alignment, simple
loop condition alignment and same-object/index/length reuse. It found zero
success-edge sites, zero loop-proven sites and zero repeated-check sites.
Therefore `AVOIDABLE_DYNAMIC=0`, despite material required safety work.

The first observed boundary is the Assembly-to-emitter contract: Assembly
contains control shape and operands but no explicit range fact annotation.
Earlier IR/SSA loss is not proven by the available public artifacts.

The strongest candidate is loop-proven bounds fact reuse, but it is not
promoted. The next discriminating question is whether a future proof-bearing
loop-carried access can preserve object/index/length identity through the
Assembly contract while closing alias, call, mutation, lifetime, overflow and
failure-order invalidators.
