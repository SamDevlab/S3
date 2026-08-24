# M2.94 Source/Workspace Boundary

M2.94 adds a bounded, deterministic contract for source units supplied by a
host service. It validates canonical relative paths and lowercase SHA-256
digests, orders units by path, and compares the Python reference with an S3
candidate using metadata projections.

No source text is loaded. There is no filesystem or network I/O, no change to
the existing driver, no benchmark, and no global T4. The milestone does not
claim full self-hosting.

## LOCAL GATES

- Focused M2.94 contract: PASS, 7 tests on Python 3.11, 3.12 and 3.13.
- `compileall bootstrap/s3`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- Affected profile: PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- M2.94 shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Adjacent M2.92/M2.93 contracts: PASS, 9 tests.
- Final tested source head: `14f82823381592015cfc87c736dd6c281b1a0cd3`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.
