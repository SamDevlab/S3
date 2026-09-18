# S3 1.2 Compiler Substrate Representability Matrix

Base main: `d31b1577a29cb95a8cdca4c865948ffa30e61364`

This checkpoint records the bounded substrate evidence. It does not authorize
self-hosting re-entry or claim a compiler implementation.

## Structures

| Structure | Status | Evidence |
| --- | --- | --- |
| SourceView / Cursor | `REPRESENTABLE_NOW` | deterministic UTF-8 path order, bounded byte cursor, LF/CRLF V1 contract |
| Token | `REPRESENTABLE_NOW` | ordinary `Token` record and local `vector<Token>` probe |
| AST/HIR Node | `PARTIALLY_REPRESENTABLE` | ordinary `Node` record and local vector probe; no parser |
| ScopeId / Scope | `REPRESENTABLE_NOW` | direct arena IDs, parent links, nested lookup and rollback |
| DeclarationId / Declaration | `REPRESENTABLE_NOW` | direct IDs plus type/storage/mutability/span metadata |
| TypeId / TypeInfo | `PARTIALLY_REPRESENTABLE` | deterministic name-to-ID table; no type system metadata |
| FunctionId | `REPRESENTABLE_NOW` | deterministic function name-to-ID table |
| StorageId | `REPRESENTABLE_NOW` | direct ID domain and declaration association |
| BlockId / Block | `PARTIALLY_REPRESENTABLE` | direct ID domain and ordinary record shape |
| ValueId / Value | `PARTIALLY_REPRESENTABLE` | direct ID domain and ordinary record shape |
| InstructionId / Instruction | `PARTIALLY_REPRESENTABLE` | direct ID domain and ordinary record shape |
| Verifier state | `BLOCKED` | verifier is deliberately outside this increment |
| Emitter/output state | `PARTIALLY_REPRESENTABLE` | bounded transactional `OutputSink`; no emitter |
| Whole-program compiler context | `PARTIALLY_REPRESENTABLE` | sources, IDs, lexical state, tables, shapes, and output compose; phases absent |

Aggregate context fields store integer IDs where the current language rejects a
composite vector as an aggregate field. Composite records and vectors are
still exercised as local ordinary-S3 values, matching the existing M1.61
representability boundary.

## Gate accounting

| Gate | State | Boundary |
| --- | --- | --- |
| Gate 2, representability matrix | `PARTIAL` | substrate rows are closed; parser/IR/verifier rows remain partial or blocked |
| Gate 4, composition-root state | `PARTIAL` | `CompilerContext` and `CompileResult` are shapes only |
| Gate 5, structured syntax | `PARTIAL` | Span/Token/Node shapes only; no syntax pipeline |
| Gate 6, semantic arena design | `PARTIAL` | scopes, symbols, declarations, type/function identity tables present |
| Gate 7, IR storage feasibility | `PARTIAL` | Block/Value/Instruction shapes and IDs only |
| Gate 9, output state | `PARTIAL` | OutputSink transactions present; no emitter |
| Gate 10, transaction/allocator model | `PASS` for substrate scope | direct IDs, bounded checkpoints, undo-log rollback, no whole-context copy |
| Gate 11, complexity budget | `PASS` for substrate scope | bounded complexity model is documented and tested |
| Gate 15, self-host authorization | `UNCHANGED` | re-entry remains `NO` |

## Validation evidence

- Hosted text-map O0/O1: pass.
- Linux x86-64 text-map native matrix: pass for new, len, capacity, reserve,
  put, contains, get, remove, key_at, value_at, clone, UTF-8 equality,
  replacement order, compaction, and clone independence.
- Hosted/native differential assertions: pass for the text-map matrix.
- Substrate corpus: 128 meaningful cases, pass.
- Soak: 3 clean-process test passes, zero observed nondeterminism.
- Adjacent ordered-map, generic-map, vector, composite-vector, AI contract,
  and architecture tests: pass.
- Windows full-suite execution completed with exit `0` and no failed tests;
  the retained terminal transcript does not preserve the pass/skip split.
- The Linux full suite completed once on the real FEATURE worktree under
  Python 3.14.4: `3609` selected, `3608` passed, `1` skipped, `0` failed,
  `0` errors. The direct status line was not captured, so exit `0` is inferred
  from the complete `[100%]` transcript and absence of failure/error markers.
- Python 3.13 was unavailable in the guest, so Linux evidence is not canonical
  Python certification.

## Complexity model

- text-map lookup: `O(n)` entries and `O(k)` bytes for a candidate key;
- symbol interning: linear text-map lookup plus one bounded clone on first use;
- scope lookup: `O(depth)` lexical parents;
- arena append/access: amortized `O(1)` append and `O(1)` ID access;
- context checkpoint: `O(number of named arenas)` cursor capture;
- rollback: `O(changes since checkpoint)` plus arena removals;
- source traversal: `O(1)` per byte and `O(n)` for a complete view;
- output append: `O(bytes appended)` with no truncation.

No operation reconstructs IDs by rescanning source or clones the whole context
for a checkpoint.

## Closure evidence

The focused closure gates completed before the full-suite runs:

- `python -m compileall -q bootstrap tools tests`: pass.
- `git diff --check`: pass.
- Windows focused substrate, adjacent-contract, hosted/native text-map, and
  three-process soak checks: pass.
- Linux focused substrate, adjacent-contract, hosted/native text-map, and
  three-process soak checks: pass under the repository VM's Python 3.14.4.
- The Windows full suite was executed once and exited `0` with no failed
  tests. Its retained terminal transcript did not preserve the pass/skip
  split.
- The earlier copied-snapshot Linux full run is retained only as the source of
  the `123`-node diagnostic corpus. Its raw failure cache was preserved before
  any later execution and was not used as the final FEATURE result.

This full-suite Linux result is a closure limitation, not a self-hosting
authorization. No compiler phase, Stage1 V4 implementation, release, tag, or
PyPI publication is part of this increment.

The first GitHub Actions run for the Draft PR was also blocked before job
execution: run `35306528596` reported ten failed jobs, each with
`runner_id=0` and an empty `steps` list. This is recorded as
`CI_STATE=INFRASTRUCTURE_BLOCKED_PRE_EXECUTION`; no workflow was rerun.

The targeted Linux closure used real Git worktrees at base `d31b1577` and
feature `5a81a5d`. Of the retained 123 IDs, 121 valid IDs expanded to 560
cases and passed identically on both sides; two stale `m162` parameter IDs
were invalid in both environments. The final feature worktree full run
completed with 3608 dots, one skip, no failure/error marker, and no
`lastfailed` cache. Python 3.13 was unavailable, so this is Python 3.14.4
evidence rather than canonical 3.13 certification.
