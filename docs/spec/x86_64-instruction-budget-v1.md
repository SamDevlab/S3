# x86-64 Instruction Budget Modes v1

## Scope

Instruction-budget selection changes only native x86-64 instrumentation. It
does not change S3 syntax, IR, serialized IR, Assembly format, diagnostics, or
the hosted emulator.

`X8664Backend(instruction_budget_mode=...)` accepts:

- `InstructionBudgetMode.PER_INSTRUCTION` (default);
- `InstructionBudgetMode.EXACT_SEGMENT` (explicit experimental mode).

The default remains `PER_INSTRUCTION`; generating native assembly without a
mode is byte-identical to explicitly selecting that mode for the frozen
control fixtures.

## Accounting semantics

Both modes count logical Assembly instructions against one execution-wide
limit. Fused native lowering does not reduce the logical weight: a `TCMP`
followed by `TBR3` still consumes two logical instructions. Calls and
re-entrant FFI callbacks share the same generated counter according to the
existing process-budget lifetime contract.

`PER_INSTRUCTION` checks the counter immediately before each logical
instruction. `EXACT_SEGMENT` partitions each basic block into contiguous
segments and never crosses a block boundary, call, branch, or return. A fast
segment is eligible only when it has at least two instructions and its total
weight does not exceed the configured limit. The fast path checks and
precharges the whole segment; a cold/slow path executes the same logical
instructions with individual checks. Short, oversized, and otherwise
ineligible segments always use per-instruction checks.

The segment planner is deterministic and exposes diagnostics for segment
boundaries, logical weights, barrier classes, and fast-path eligibility. The
slow path preserves instruction-limit failure context and non-budget runtime
failures. Exact accounting is not a relaxed or approximate budget.

## Selection and compatibility

The mode is currently selected through the x86-64 backend API; no source
syntax, command-line default, or project-wide policy changes implicitly.
Changing the default requires a separate explicit decision after correctness,
code-size, and representative-workload evidence. No public artifact version
is bumped by this backend-only option.
