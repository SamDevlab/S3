# E0 Instruction-Budget Equivalence

## Observable contract

The oracle is the current per-instruction count-up emitter. Before each
logical S3 Assembly instruction, it fails if the count has reached the limit;
otherwise it increments once and executes that instruction. Exact-segment
mode must preserve success/failure, result, side effects before exhaustion,
failure site/context, call lifetime, and standalone behavior for serial
execution.

## Evidence implemented

The focused native suite compares exit status, stdout, and stderr between
`PER_INSTRUCTION` and `EXACT_SEGMENT` for:

- exact single-segment budgets `W-1`, `W`, and `W+1`, plus zero-budget input
  rejection;
- a bounded loop with repeated S3 calls, branch/backedge execution, and limits
  spanning early, middle, and successful paths;
- non-budget bounds failure inside a fast-eligible segment;
- repeated serial calls into one shared artifact, proving process-persistent
  budget lifetime;
- a foreign callback that synchronously re-enters an exported S3 function;
- an externally visible callback side effect immediately before and after a
  budget boundary;
- the maximum accepted unsigned 64-bit instruction limit.

The callback probes check byte-for-byte equality of status, output, and
diagnostic stream for both modes. The new native test module currently reports
22 passing tests in the Linux x86-64 VM with native execution required.

## Scope boundary

The result is E0 for serialized execution only. Concurrent host-thread calls
are not part of the established contract because the shared counter is
unsynchronized and segment precharge changes when another thread could observe
count progress. No claim is made for concurrent FFI use.

The full S3 suite and source-freeze gates are recorded separately in
`EXPERIMENTAL_VALIDATION.md`; this note alone does not authorize benchmarking
or promotion.
