# Stage1 Bootstrap IR Closure

## Candidate

- `FINAL_TESTED_SOURCE_HEAD=2d7385c6813395239bc68b6b2858da12a693b160`
- `T4_TESTED_HEAD=eaf3ec0b7415b408f3b7c041244db5cfe7739b1e`
- `SOURCE_CHANGED_AFTER_T4=NO`
- `T4_RERUN_REQUIRED=NO`
- branch: `feature/actual-stage1-compiler-seed-20260824`
- PR: `#268`, Draft, no merge

## IR closure

The historical one-`OP_RETURN`-per-function audit is preserved in
`self-source-ir-audit.json`. The new bounded structural audit records 30
functions (25 local and 5 foreign), 64 parameters, 23 locals, 325 blocks, 1212
instructions, 926 values, 366 calls, 104 branches, 6 loops, and 103 returns.
Function identity, foreign/local kind, event operands and offsets, call
argument lanes, values, and control targets are represented and checked.

```text
SELF_LEX=PASS
SELF_PARSE=PASS
SELF_SEMANTIC=PASS_BOUNDED
SELF_IR=PASS_LOSSLESS_BOOTSTRAP_SUBSET
SELF_VERIFY=PASS_LOSSLESS_BOOTSTRAP_SUBSET
GENERAL_EMITTER=BLOCKED_NEW_IR_NOT_YET_SUPPORTED
FIRST_SELF_COMPILE_BLOCKER=EMITTER_CAPABILITY
STAGE1_TO_STAGE2=NOT_STARTED_THIS_ROUND
FULL_SELF_HOSTING=NO
```

The qualification is deliberately scoped. Independent parameter/local
type-mutability tables and a canonical IR byte digest are not claimed by this
round. The simple-return emitter remains the only executable emission path.

## Linux qualification

Two builds of the frozen source on `s3-vm` were byte-identical:

- artifact: `41f4ac5dd17d042bb3f448f9c9878e6e52aae1ccf8d6ba793205e1a3b9121c7e`
- Assembly: `512044229ba5a4035c1d862ee167839e96e95a029556e01a6d97b26871d03be0`

The supported native corpus exited `0, 7, 8, 180, 255` for source values
`0, 7, 8, 180, -1`; invalid input returned `S3_STAGE1_ERROR`.

## Final T4

The final T4 was executed exactly once at `T4_TESTED_HEAD` and preserved in
`t4-final-20260824-174039.raw.txt`:

```text
T4_SELECTED=454
T4_PASS=453
T4_FAIL=0
T4_TIMEOUT=1
T4_EXIT=1
```

The sole timeout was `tests/test_stage1_compiler_seed.py` with
`timeout_class=DEFAULT` and `applied_timeout_seconds=60`; the captured output
tail was `....`. It is recorded as a real timeout, not converted into a pass.
No T4 rerun is required because no executable/compiler/test logic changed
after this run; subsequent changes are documentation/evidence only.

## Scope boundary

No benchmark, Stage2, Stage3, general emitter, merge, or release was started.
