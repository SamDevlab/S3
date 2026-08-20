# M1.91-M2.00 Entry Criteria

The following gates apply before M1.91 implementation begins and are inherited
by later milestones unless a milestone contract strengthens them.

1. The predecessor line is merged into canonical `main`, and the exact merge
   commit is recorded. For this campaign the canonical predecessor is
   `a9e430551f2ee77aa2ef229daf9e967333e83e2c` (PR #183).
2. The local campaign checkout must be on
   `feature/m191-m200-autonomous-20260819`, based on that canonical predecessor
   or an explicit documentation-only descendant, and the working tree must be
   clean before implementation starts.
3. Milestone contract, dependency edges, non-goals, security/resource limits,
   and test/benchmark protocol must be reviewed before changing production
   source for that milestone.
4. A focused test inventory must exist before implementation. Native/platform
   evidence must be classified as executable, structural, or deferred.
5. No previous failure may be hidden by a skip, fixture rewrite, benchmark
   special case, force push, rebase, result relabeling, or history rewrite.
6. Milestones execute sequentially on the campaign branch. A later milestone
   may not begin until the previous milestone has a recorded focused/cross-layer
   closure and no unresolved blocker/high finding. This campaign intentionally
   uses one branch and one final PR while preserving milestone boundaries.
7. T0/T1/T2 focused gates run continuously; T3 runs when impact justifies it.
   Exactly one campaign-closing T4 is allowed after M2.00. A failing/timeout T4
   is preserved verbatim and triaged rather than rerun merely to make evidence
   green.
8. Local gates are authoritative for campaign readiness. GitHub Actions/checks
   are supplementary unless an explicit repository policy is recorded for this
   campaign; pending or skipped remote checks alone are not a local blocker.
9. Correctness fixtures must be deterministic and local. Public services are
   not correctness dependencies. Benchmark timing requires an independent,
   pinned reference before any comparative claim.
10. No tag, release, package publication, branch deletion, force push, or
    M2.01+ implementation is authorized by the campaign.

Current base state:

```text
M191_M200_EXISTING_ROADMAP_FOUND=NO_SUBSTANTIVE_PREEXISTING_ROADMAP
M191_M200_PREPLAN_CREATED=YES
M181_M190_CANONICAL_PREDECESSOR_MERGED=YES
M181_M190_CANONICAL_PREDECESSOR_SHA=a9e430551f2ee77aa2ef229daf9e967333e83e2c
M191_M200_REMOTE_BASE_PREPARED=YES
M191_M200_IMPLEMENTATION_STARTED=NO
M191_LOCAL_CHECKOUT_VERIFIED=NO_PENDING_USER_LOCAL_SYNC
M191_ENTRY_CRITERIA_SATISFIED=NO_PENDING_LOCAL_BASELINE_VERIFICATION
```

The last field remains `NO` until the local campaign checkout is synchronized,
its exact HEAD is recorded, and the working tree is confirmed clean. That local
verification is an entry check, not implementation work.
