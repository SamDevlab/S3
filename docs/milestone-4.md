# Milestone 4: conservative global dead-store elimination

## Source and scope

ADR-0016 lists global DSE as future work after the correctness foundation. The
existing DSE is intra-block. This milestone adds only the whole-function proof
that a frame-local memory object has no `LOAD` anywhere in the function.

## Safety contract

S3 has no pointers and memory objects belong to a function frame. A call cannot
observe a caller's frame-local object. Therefore stores to an object with no
load have no observable consumer. Any object with a load remains untouched by
this pass; path-sensitive and alias-sensitive global proofs are out of scope.

## Acceptance

- the pass preserves SSA and verifier validity;
- cross-block stores with no load are removed;
- loaded objects and existing local DSE cases are preserved;
- O0/O1 behavior remains equivalent;
- the pass is separately named and represented in the SSA contract inventory.
