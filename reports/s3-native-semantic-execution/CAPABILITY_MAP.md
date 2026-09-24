# Native Semantic Execution Capability Map

Checkpoint after the first i64 semantic execution slice.

The semantic path is implemented in S3 source and is compiled by the existing
S3 compiler. The focused tests execute that compiled path through the hosted
emulator on the current Windows host. The Linux x86-64 qualification test is
present but skipped outside Linux x86-64; no native Linux result is claimed by
this checkpoint.

| Capability | Frontend | Semantics | Lowering / execution path | Linux x86-64 qualification |
| --- | --- | --- | --- | --- |
| Integer literals | PASS | PASS | PASS for bounded positive i64 literals | NOT RUN on current host |
| Identifiers | PASS | PASS | PASS in native semantic environment lookup | NOT RUN on current host |
| Local binding | PASS | PASS | PASS for ordered i64 bindings | NOT RUN on current host |
| Assignment | PASS | PASS | PASS for local read-after-write | NOT RUN on current host |
| Binary `+` / `*` | PASS | PASS | PASS for i64 expressions | NOT RUN on current host |
| Comparisons | PASS | PARTIAL | `<` is used by the executable while slice | NOT RUN on current host |
| Function parameters | PASS | PASS | PASS for i64 arguments | NOT RUN on current host |
| Function calls | PASS | PASS | PASS through native semantic function frames | NOT RUN on current host |
| Return | PASS | PASS | PASS for i64 return propagation | NOT RUN on current host |
| Multiple functions | PASS | PASS | PASS for named callee lookup and calls | NOT RUN on current host |
| `while` | PASS | PASS | PASS for the single-assignment executable slice | NOT RUN on current host |
| `f64` scalar execution | PARTIAL elsewhere in S3 | NOT IMPLEMENTED here | BLOCKED by missing native float token/value path | NOT RUN |
| Indexed numeric data | REPRESENTED elsewhere in S3 | NOT IMPLEMENTED here | DEFERRED until a native value/layout contract is selected | NOT RUN |

## Evidence

- `tests/test_native_semantic_execution.py`: i64 literals, bindings,
  assignment, calls, grouping, and while execution; arbitrary literal values
  include `0`, `1`, `7`, `17`, `100`, and `999`.
- `tests/test_native_frontend_slice.py`: adjacent native frontend regression
  matrix remains green.
- `python -m compileall bootstrap/s3`: PASS.
- `git diff --check`: PASS.
- The Linux x86-64 test is intentionally environment-gated and remains an
  explicit pending qualification on Windows.

## Current architectural frontier

The native substrate scanner currently emits integer, word, punctuation,
newline, and EOF records. It does not yet emit float tokens, and the new
semantic environment stores only i64 values. Closing f64 therefore requires a
real token/value representation decision rather than a test-only extension.
Indexed data likewise requires a native semantic value and layout contract;
the existing hosted vector facilities are not silently treated as that
contract.
