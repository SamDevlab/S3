# Exact Segment Instruction-Budget Experiment

Status: experimental; default backend behavior remains per-instruction.

## Scope

This branch tests whether the x86-64 emitter can amortize the existing global
count-up instruction budget over exact logical segments. It does not change
the S3 language, Assembly format, instruction weights, or default mode. The
experiment is selected only through the internal `X8664Backend` option
`InstructionBudgetMode.EXACT_SEGMENT`; ordinary `generate_native_assembly`
continues to use `PER_INSTRUCTION`.

## Planner contract

`plan_budget_segments(AssemblyFunction)` consumes validated Assembly objects,
not emitted x86 text. A segment belongs to one function and one basic block,
contains contiguous logical instruction indexes, and has weight equal to the
number of indexes it contains. The plan ends a segment at `TCALL`, `TBR3`,
`TJMP`, or `TRET`, including that barrier instruction. It never carries work
across a block edge. Ineligible weight-one segments and segments heavier than
the configured limit retain scalar per-instruction accounting. The fixed
minimum fast weight is two.

Fused native lowering does not change logical weight. In particular, a fused
`TCMP`/`TBR3` pair weighs two, and the scalar fallback instruments both
instructions.

## Fast and exact fallback paths

For current count `C`, limit `L`, and segment weight `W`, the fast path is
eligible only when `W >= 2`, `W <= L`, and `C <= L - W`. This avoids
underflow and counter overflow. It adds exactly `W` to the existing count-up
counter before executing the segment. If the condition is false, the duplicated
cold path uses the existing check/increment before every logical instruction,
preserving the exact failure instruction and its diagnostic context.

A call may be the last logical instruction of its caller segment, but no
caller instruction after the call is precharged. The slow copy is unreachable
on fast fallthrough: ordinary segments jump over it, while branch/jump/return
segments transfer control or terminate.

## Explicit limitations

The count-up field is process-global and unsynchronized in the baseline
runtime. This experiment establishes equivalence for serial native execution,
including serial repeated FFI calls and synchronous foreign-callback reentry
at the `TCALL` barrier. Concurrent host-thread entry into one artifact is not
qualified: another thread could observe a segment's aggregate increment
between its logical instructions. Neither this experimental mode nor the
baseline is documented as thread-safe, and no concurrent E0 claim is made.

The mode is not a production interface, is not selected by the CLI, and is not
the default. No production-readiness, release, or merge decision is implied.
