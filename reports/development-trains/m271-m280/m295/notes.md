# M2.95 Bounded Compiler Driver

M2.95 composes the source/workspace metadata boundary, canonical IR
verification, Assembly verification and explicit native planning. The S3
candidate compares only deterministic identities supplied by the host-side
composition.

No source is loaded, no filesystem or network service is invoked, and no
assembler/linker is called. This is not a full compiler or a self-hosting
claim.

## LOCAL GATES

- Focused M2.95 contract: PASS, 5 tests on Python 3.11, 3.12 and 3.13.
- `compileall bootstrap/s3`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- Affected profile: PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- M2.95 shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Adjacent M2.92/M2.93/M2.94 contracts: PASS, 21 tests.
- Final tested source head: `9d599b62f3cb4b99fb2ded894e1d50fef17cc18d`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.
