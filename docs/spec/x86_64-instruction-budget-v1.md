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

`PER_INSTRUCTION` charges one logical instruction immediately before it
executes. With register allocation enabled and a limit no greater than
`INT64_MAX`, native code keeps the remaining process budget in a reserved
callee-saved register and uses a decrement/sign check for each instruction.
It synchronizes the remaining budget at S3 and foreign call boundaries, so
serial calls and synchronous FFI re-entry share the same artifact-local
budget. The register is saved/restored according to the System V ABI. When
register allocation is disabled or the configured limit exceeds
`INT64_MAX`, code generation retains the original memory-counter sequence.
Concurrent entry into the same loaded artifact from multiple host threads is
not currently supported or qualified. This clarifies the current execution
contract; it does not permanently prohibit concurrency. Future support requires
an explicit contract for execution context, budget ownership, frame accounting,
and synchronization.

`EXACT_SEGMENT` partitions each basic block into contiguous
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
