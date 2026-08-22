# PR191 Explicit Integration Decision

The live state matches the reviewed candidate. `origin/main` remains exactly
`9b39c7070d7bfa23d709c2128eb0b0bbef164177`, and PR #191 remains open, Draft,
unmerged, and mergeable at `e72602b8860d480f9b0bec2f43f4ac6ebbf22333`.

The review source lock `d10532c0f2e2db07f1d342bd6c3dcc3c782199ae` is an
ancestor of the PR HEAD. The only post-lock commit is the reports-only commit
`e72602b`; no source, test, tool, runtime, or compiler behavior changed after
the lock. The diff remains narrow: one production emitter file, one regression
test file, and report artifacts, with no unrelated files.

The unsafe TMOV alias symbols remain absent from the x86-64 backend. Existing
evidence is traceable to the locked source: T1 is 74/74, T2 is 220/220, the
targeted Linux checks pass, the F64 native case passes, and the frozen V2.2
matrix is 100/100. No timing, T4, or full suite was run. GitHub reports no
checks for this branch, and there are no reviews, issue comments, requested
changes, or unresolved correctness/scope concerns.

The RC1 tag remains immutable and its known TMOV correctness defect remains a
historical fact. PR #190 remains open, Draft, unmerged, and untouched; its V2.2
correctness blocker is cleared only in the disposable combined evidence.

The technical decision is `APPROVE_FOR_EXPLICIT_MERGE`. The recommended future
method is `MERGE_COMMIT`, consistent with recent main history and preserving
the forensic commit provenance. No merge was performed. A later campaign must
capture the factual merge SHA, revalidate the minimal reproducer and A07 from
main, establish the post-fix baseline, and reconcile PR #190 separately.
