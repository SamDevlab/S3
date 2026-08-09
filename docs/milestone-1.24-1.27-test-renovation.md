# Milestones 1.24-1.27 - Test Renovation Campaign

This checkpoint records the completed test-infrastructure campaign after
Milestone 1.23. It changes test execution and test infrastructure only; it
does not add language features, references, pointers, aliasing, heap storage,
or a new ABI or allocator.

## Delivered

- **1.24:** consolidated the slow tokenizer corpus into one bounded O0/O1
  execution per corpus while preserving every case and assertion.
- **1.25:** removed duplicate renderer and benchmark matrix executions. Unit
  coverage remains on Python 3.11, 3.12, and 3.13; renderer and benchmark
  groups have one canonical Python 3.13 execution.
- **1.26:** added bounded fixed-seed generated differential cases and an
  explicit CI gate for them. Generation uses a local seeded RNG and produces
  reproducible source, seed, and expected-value tuples.
- **1.27:** consolidates this campaign record and its merge evidence.

## Merge Evidence

| Milestone | PR | Merge commit |
|---|---:|---|
| 1.24 | #143 | `d35eefc467987c578704b1d9a67793466e8d4d1c` |
| 1.25 | #144 | `ad9aab2d1e7308e2dd17f3d8f8b10bf449bd445f` |
| 1.26 | #145 | `8705d79895d9f85c3bafbd263e93a4c7efcbe1d0` |

Each PR was validated by natural CI, promoted from Draft only after all
checks passed, merged with a protected merge commit, and verified as an
ancestor of `origin/main`.

## Scope Boundary

No runtime production implementation was changed by this campaign. The next
milestone is intentionally outside this checkpoint; no Milestone 1.28 work
was started.
