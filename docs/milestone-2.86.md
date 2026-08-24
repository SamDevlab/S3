# M2.86 Ownership / Reference Lowering

Experimental bounded lowering for scalar fixed-layout places, shared/mutable
references, initialization, reads/writes, and move invalidation. The S3
candidate is currently observed through real S3 diagnostics and partial
scalar computation; complete place/reference/operation/state lane
reconstruction remains pending. Python is reference, harness, and
orchestrator only for the eventual exact proof. Heap ownership and full aggregate ownership
are out of scope. Aggregate scope is ordered scalar result/reference
propagation only; M2.83 reuse is not yet claimed.

Shared writes, mutable borrows of immutable places, invalid references,
borrow conflicts, uninitialized reads, and use-after-move have S3-observed
diagnostic coverage in the bounded subset. Exact positive differential,
complete state lanes, direct M2.84 mapping, and full M2.85 ownership join
semantics remain deferred. No new frontend syntax is added.
