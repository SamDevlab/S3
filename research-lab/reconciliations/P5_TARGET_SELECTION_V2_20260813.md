# P5 target selection v2 reconciliation

## Checkpoint

The campaign rebased from `origin/main=1a775ba79f3abb6d3b33bb7d710ab67d0f808e18`
and preserved the historical P4, PR #172, and PR #173 conclusions. The new
whole-backend corpus has 15 workloads, including six exact JSMN fixtures and
nine controls across integer, calls, branches, references, slices, f64, trit,
and tryte domains.

## Evidence

Aggregate O1 Linux native output was 305146 instructions, 17104476 text bytes,
74031 memory operands, 44591 frame accesses, 76034 branches, and 45579 address
calculations. Dynamic opcode traces were dominated by TCONST/TSTORE/TLOAD, but
the reference/slice fallback trace is explicitly incomplete for dynamic
memory attribution. True spills remain `NOT_ESTABLISHED`; repeated dynamic
addressing is `NOT_ISOLATED`.

## Selection

The strongest bounded target was the native x86-64 emitter's per-instruction
instruction-limit guard. For representable limits, `cmp [rip + counter], imm32`
replaces the unnecessary `movabs r11` materialization; wider values retain the
old exact fallback. A 15-workload Linux prototype passed all native executions
and reduced aggregate O1 instructions by 14488 (-4.748%) and text by 289760
bytes (-1.694%), without changing memory operands, frame accesses, branches, or
address calculations.

The production implementation is one commit, `a615d298b8d72f355a03e8abb2df5bd5a58d4758`,
in PR #174. Focused tests and the exact-head full suite passed. Natural CI was
still pending for the renderer shard at the time of this checkpoint; all other
observed checks were green. P6 and shutdown remain prohibited.
