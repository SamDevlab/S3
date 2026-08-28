# Overnight revision 34 — gated Stage1 → Stage2 → Stage3 campaign

This campaign consumes revision 33 provenance analysis and authorizes autonomous overnight progress only through explicit proof gates.

## Safety invariant

Never convert missing evidence into PASS. Never invent a checkpoint. Unknown = UNKNOWN/NOT_PROVABLE. Stop at the first concrete blocker that cannot be repaired narrowly and safely.

The original dirty worktree remains evidence-only and MUST NOT be modified or cleaned.

Dirty worktree:
`C:\Users\samue\Downloads\S3\S3-actual-stage1-compiler-seed-20260824`

Clean worktree base:
`C:\Users\samue\Downloads\S3\S3-PR268-Clean-Rev32`

Recovery package:
`C:\Users\samue\Downloads\S3\S3-PR268-Recovery-Rev31-20260827-214412`

Base commit:
`d67da9ea7dc8b83b0b80adb681011717eebec616`

Frozen semantic handoff:
`c12e45d646af27f85b39c391d3a7645a812b28c5`

Authoritative protocol: S3IR2 v2.

## Overall route

1. Finish Rev33 provenance graph.
2. Create an isolated overnight branch/worktree from exact d67da9e if needed; do not mutate dirty evidence worktree.
3. Reapply only the minimum proven Stage1 waves in causal order.
4. Validate each wave before the next.
5. Close Stage1 semantic/compiler requirements needed for SELF_EMIT.
6. Perform SELF_EMIT only after Stage1 closure evidence.
7. Produce Stage2.
8. Use Stage2 to produce Stage3.
9. Compare Stage2 and Stage3 using deterministic/observable equality required by the project; report exact hashes and any permitted normalized comparison.
10. Run the authorized correctness test matrix.
11. Run benchmarks only after correctness/self-hosting gates pass.
12. Write final overnight report with exact commands/results/hashes/first blocker.
13. After report is flushed to disk, schedule Windows shutdown with a short delay.

## Stage1 gate

Stage1 is NOT considered closed merely because a candidate file exists.

Required evidence should include, as applicable to the existing repository contracts:
- bindings/typed values;
- instruction def/use;
- call dataflow;
- complete terminators;
- canonical deterministic serialization;
- general emitter closure;
- native build on the supported Linux x86_64 environment;
- focused probes/tests tied to the exact Stage1 candidate hash;
- no unresolved verifier errors for the required self-hosting subset.

S3IR2 completeness lanes:
- S1 typed value definitions = 1
- S2 instruction def/use = 2
- S3 call dataflow = 4
- S4 complete terminators = 8
- S5 canonical serialized IR = 16
- full completeness = Z31

Do not claim full semantic closure below Z31 unless the repository's exact current self-hosting contract explicitly defines a narrower gate and records it. The hosted oracle is support evidence, not native Stage1 evidence.

## Repair policy

When a validation fails:
1. capture exact command, stdout/stderr, exit code, candidate hash, first concrete failure;
2. determine whether failure is deterministic and attributable;
3. make only the narrowest source/test/tool edit necessary;
4. rerun the smallest relevant validation first;
5. then rerun the gate;
6. do not broaden scope while a concrete blocker remains.

Do not rewrite large subsystems merely to make a test green.

## Commits

Use a dedicated overnight branch derived from exact d67da9e. Suggested name:
`recovery/pr268-overnight-stage123-20260827`

Small commits are allowed only after a gate or coherent repair slice passes locally. Do not merge any PR. Do not force-push. Do not rewrite PR268 history. Push of the dedicated overnight branch is allowed only after at least one validated checkpoint and only if normal non-force push succeeds. If remote policy rejects it, continue locally and report the failure; do not work around protections.

## Original dirty worktree

Forbidden:
- reset
- restore
- clean
- delete
- checkout that discards changes
- applying new edits there

Use it only read-only for provenance comparison.

## Stage2 gate

SELF_EMIT is authorized only after Stage1 closure is actually proven.

Record:
- exact Stage1 source/candidate SHA256;
- exact Stage1 native executable SHA256;
- exact self-emit command;
- exit code;
- emitted Stage2 path;
- Stage2 SHA256/bytes;
- compiler/runtime diagnostics.

If SELF_EMIT fails, Stage2 = NOT_CREATED or FAILED, capture the first concrete failure, repair Stage1 narrowly if attributable, and retry the minimum gate. Do not fake Stage2 by copying Stage1 artifacts.

## Stage3 gate

Only after a real Stage2 compiler exists and passes the minimum required smoke/build gate:
- use Stage2 to compile the same canonical compiler source into Stage3;
- record exact command, exit code, hashes and paths;
- do not produce Stage3 by copying/renaming Stage2.

## Equality/determinism gate

Compare Stage2 and Stage3 according to project rules.

Prefer byte equality when the project expects reproducible byte-identical output. If the repository defines a normalized semantic/observable comparison because known metadata differs, run both raw and normalized comparisons and identify every permitted difference.

Never call equality PASS if the comparison method is invented during the run.

Record at minimum:
- Stage2 SHA256
- Stage3 SHA256
- byte sizes
- byte equality YES/NO
- normalized/observable equality only if an existing verifier or documented contract exists
- first differing offset or first semantic mismatch on failure

## Correctness tests

Run tests in escalating cost order after self-hosting gates, unless a smaller test is needed during a repair:
1. exact focused Stage1 semantic/conformance tests;
2. Stage1 native compiler tests;
3. Python/unit/static verification relevant to compiler bootstrap;
4. existing differential/generated tests required by the repository;
5. full feasible correctness suite.

Use the project's supported environments. Historical Linux environment:
- SSH alias: s3-vm
- host: Ubuntuserve
- Python: `/home/vboxuser/.cache/s3-pr268-venv/bin/python`
- cc: `/usr/bin/cc`

Do not use plain `python` on the Linux guest when the project contract requires the venv interpreter.

If an unrelated repository test fails, classify it as unrelated only with concrete evidence. Otherwise report cause as NOT_ATTRIBUTED.

## Benchmark gate

Benchmark is strictly last.

Run only after:
- Stage1 closed;
- real Stage2 produced;
- real Stage3 produced;
- required Stage2↔Stage3 equality/determinism gate passed;
- correctness tests required for the campaign passed or have an explicitly proven unrelated failure classification.

Use existing S3-Benchmarks/benchmark harnesses and repository commands. Do not invent performance claims. Report environment, commands, iterations, warmup if defined, raw measurements, aggregate statistics produced by the existing harness, and hashes of compilers used.

No benchmark result may be presented as a regression/improvement without a valid comparable baseline under the same benchmark contract/environment.

## Stop conditions

Stop forward semantic progression on any of:
- provenance not sufficient to identify a safe reapplication wave;
- clean worktree no longer has understood provenance;
- canonical source provenance conflict;
- candidate hash mismatch with claimed validation evidence;
- non-deterministic unexplained validation failure;
- self-emit failure not attributable to a narrow Stage1 issue;
- Stage2 not actually executable as the compiler required for Stage3;
- Stage2↔Stage3 comparison fails without a narrow attributable bug;
- test infrastructure itself is broken and cannot be safely repaired without broad unrelated changes;
- remote/Git state requires destructive or force operations;
- any instruction would require guessing.

On stop, write a complete blocker checkpoint instead of continuing into later stages.

## Final report

Write outside the original dirty worktree, preferably under the Rev31 recovery package:
`OVERNIGHT_FINAL_STATUS_20260828.md`

Also write raw machine-readable summaries where practical.

The final report must explicitly classify:
- PROVEN
- FAILED
- NOT_RUN
- NOT_PROVABLE
- NOT_APPLICABLE

for:
- Rev33 provenance
- reapplication waves
- Stage1
- SELF_EMIT
- Stage2
- Stage3
- Stage2↔Stage3 equality
- focused tests
- full correctness tests
- benchmark
- commits
- push

Include exact HEAD, branch, dirty status, hashes, commands, exit codes and first blocker.

## Shutdown

Only after the final report and all logs/manifests are written and flushed to disk, schedule Windows shutdown with a 60-second delay using:

`shutdown.exe /s /t 60 /c "S3 overnight campaign finished; final report saved"`

Before scheduling shutdown, ensure no Git command is still running and no file copy/write remains in progress.

If shutdown command is unavailable or rejected by permissions, report SHUTDOWN_SCHEDULED=NO with the exact error; do not attempt privilege escalation.

Shutdown is required after a normal completed campaign OR a safely documented terminal blocker. Do not shutdown in the middle of an active write/test/build.

## Never do

- no PR merge
- no force push
- no destructive cleanup of the dirty evidence worktree
- no fabricated PASS
- no benchmark before correctness/self-hosting gates
- no Stage2/Stage3 by copying files
- no changing test expectations merely to match broken output
- no suppressing failures
- no claiming hosted-oracle evidence as native self-host evidence
