# CI/P5 Autonomous Campaign Reconciliation

## Checkpoint

The campaign began from P4-complete `origin/main=a0b694fadc985c0b8e0944fb7844e14f72a838d8` and research head `d127d6592ebc5db90ca433fe7e16a1dbe0c46d7b`. The original Windows checkout was preserved with only its pre-existing untracked files. No research branch contents were merged into production.

## Real correctness finding

The old O1 slice limitation was reproduced from a valid shared/mutable slice program. O0 passed. The first invalid representation appeared after `ssa-optimizations`: SSA-to-IR lowering dropped `IRRegister` and `IRInstruction` reference metadata and parameter slice-length linkage. This was a factual correctness bug, not a stale test. PR #172 (`19b39c71fb644d2f4d923d1695eb3ac43e7e49e7`) passed natural CI, including two renderer jobs, and merged as `229811359948cf8e12848036882edaa89108a9fa`. The implementation head is ancestral to `origin/main`.

## Actions audit

The API window returned 591 runs and 5,506 jobs, totaling 22,356.616667 timestamp-derived job minutes. The user billing meter is 25,340 minutes / `$152.04` gross / `$0` billed; the REST billing endpoint was unavailable. `Tests` non-main pushes consumed 12,274.700000 minutes; 102 research-branch pushes consumed 3,716.766667 minutes. There were 197 same-SHA push/PR pairs with 8,068.350000 redundant push-side minutes. The potential superseded candidate total is 7,547.616672 minutes and is explicitly non-additive.

The exact collection returned 2,709 unique nodes. The current matrix executes 7,449 instances, with 4,740 duplicate executions. No coverage was deleted. Renderer is the dominant slow job: the two #172 natural renderer jobs took 30m15s and 34m42s. This is evidence for future sharding, not permission to remove renderer coverage.

## CI PR

PR #173 (`ae278bfdec2c9b957a1d885c2076d37f58f97df2`) is the only CI-efficiency PR. It restricts pushes to `main`, keeps executable pull-request paths, cancels stale PR runs only, enables official pip caching, and narrows M1.38 Docker paths. Python 3.11/3.12/3.13, SSA per-pass, native, differential, benchmark smoke and Docker gates remain. The trigger replay models a 54.94% reduction of historical `Tests` job minutes, excluding overlapping concurrency/cache gains.

PR #173 reached terminal green, including its 31m04s renderer job, and merged
as `1a775ba79f3abb6d3b33bb7d710ab67d0f808e18`. The implementation head and the
merge commit were both proven ancestors of `origin/main`.

## Reprofile and P5 decision

Eight representative workloads passed hosted IR and Linux x86-64 native execution. JSMN is the largest current shape: 299,903 `.text` bytes, 53,668 native instructions, 27,453 load/store-like instructions, 12,143 branches, 40 calls, and 1.494s median O1 compile/lower time in the three-sample Linux run. The result is characterization, not a universal performance claim.

The strongest residual hypothesis remains repeated memory-state materialization / metadata staging, but prior closure evidence shows most observed reset traffic is semantically justified and the unknown share is not proven removable. The O1 slice fix is correctness work, not P5. TADDR remains a separate future capability. Therefore:

```text
P5_SELECTION=NO_VALID_TARGET_YET
NO_P5_PRODUCTION_CHANGE=YES
P6_STARTED=NO
```

No campaign full suite was run because no final P5 candidate existed; no performance benchmark was used to manufacture a promotion.

## Closure

After the research branch receives this reconciliation, verify the original
checkout remains untouched and the external final JSON/report contain the
factual merge SHA. Only then execute the authorized Windows shutdown command.
