# M2.86 Ownership / Reference Lowering

Experimental bounded lowering for scalar fixed-layout places, shared/mutable
references, initialization, reads/writes, and move invalidation. The S3
candidate is observed through exact scalar lanes; Python is reference,
harness, and orchestrator only. Heap ownership and full aggregate ownership
are out of scope. Aggregate scope is ordered scalar result/reference
propagation only, with M2.83 call-plan reuse.

Shared writes, mutable borrows of immutable places, invalid references,
borrow conflicts, uninitialized reads, and use-after-move fail closed with
stable diagnostics. `M284_REAL_INTEROP=PASS_LINEAR_SUBSET`; multi-block
verifier interop remains deferred to M2.88. M2.85 control-flow composition is
accounted for structurally; no new frontend syntax is added.
