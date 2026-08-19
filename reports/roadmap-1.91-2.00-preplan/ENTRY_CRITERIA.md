# M1.91-M2.00 Entry Criteria

The following gates apply before any milestone implementation begins:

1. The preceding milestone is merged into canonical `main` and its
   implementation and merge commits have been proved ancestors of
   `origin/main`.
2. The working tree and target campaign checkout are clean, and the source
   head is recorded exactly.
3. The milestone contract, dependency edges, non-goals, security limits, and
   test/benchmark protocol have been reviewed and committed as documentation.
4. A focused test inventory exists before implementation; required native and
   platform evidence is classified as executable, structural, or deferred.
5. No previous failure is hidden by a skip, fixture rewrite, benchmark special
   case, force push, rebase, or history rewrite.
6. The candidate has a single branch and pull request, with no milestone
   stacking. The next milestone cannot start before merge.
7. A full suite and relevant native/differential gates are run on the exact
   final candidate head, with terminal exit codes recorded.
8. CI is terminal and green before Ready/Merge; pending CI is a wait state.

Current pre-plan state:

```text
M191_M200_EXISTING_ROADMAP_FOUND=NO_SUBSTANTIVE_ROADMAP
M191_M200_PREPLAN_CREATED=YES
M191_M200_IMPLEMENTATION_STARTED=NO
M191_ENTRY_CRITERIA_SATISFIED=NO
```

The final field is intentionally `NO`: M1.81-M1.90 publication is locally
certified only, and this task creates planning documents rather than a merged
canonical predecessor.
