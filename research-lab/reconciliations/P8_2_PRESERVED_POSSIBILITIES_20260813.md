# P8.2 preserved possibilities and collapse points

## Checkpoint

- Production anchor: `631b51e70562a33183ac14d0be5bbe2ddd140779`
- Research checkpoint published before this study: `d852a611f0c824436c736ff380d5cfb33d86feb5`
- Actions repository policy: disabled; no new workflow run is expected.
- Original detached checkout was preserved with its two pre-existing
  untracked artifacts.

## Model and challenger

For a value `v` at phase `p`, `P(v,p)` is a research notation for the set of
physically valid realizations still available. A collapse is recorded only
when the implementation boundary visibly removes forms. This model helps
separate location flexibility, representation flexibility, and proof-knowledge
flexibility, but it is not a proposed runtime or compiler data structure.

The simplicity challenger is a direct producer/consumer mismatch rule. It is
currently stronger for implementation: P5, P6, and P7 each had a local,
measurable consumer and a conservative fallback. A global possibility set has
not shown incremental coverage or a soundness benefit.

## Possibility collapse ledger

| ID | Family / boundary | Before -> after | Lost possibility | Required? | Evidence / status |
| --- | --- | --- | --- | --- | --- |
| C1 | control state: `TCMP -> TBR3` | semantic trit, flags, scalar -> materialized trit | direct branch on flags | conditional | Proven for same-block dead-result consumers in P7; already shipped, excluded from P8.2. |
| C2 | initialization state | known initialized fact -> native metadata byte | lazy proof-only realization | unknown | Large residual family, but failure, alias, call, and successor observers remain. No path-complete safe population. |
| C3 | memory/reference | semantic address/reference -> temporary -> memory operand | direct address-capable consumer | unknown | Address identity, provenance, mutability, and evaluation count are obligations; no measured safe fusion. |
| C4 | memory roundtrip | semantic load/store fact -> canonical frame state -> reload | direct memory-state transfer | unknown | Static golden adjacency is zero; alias and immutable/failure semantics block inference. |
| C5 | scalar location | immediate/register -> frame -> register | immediate or physical residence | conditional | Existing local TMOV/TCONST and residence mechanisms cover known cases; no new broad rule measured. |
| C6 | F64 representation | XMM value -> integer bits/frame -> XMM | direct XMM residence | unknown | NaN, ABI, call, and exact bit behavior require a targeted corpus; no opportunity count. |
| C7 | slice/reference metadata | base+length/provenance -> decomposed fields -> reconstructed metadata | direct metadata residence | unknown | Length, provenance, mutability, and evaluation count are semantic; no dynamic evidence. |

The complete required field set for every candidate (`VALUE_FAMILY`,
`PHASE_BEFORE`, `POSSIBILITIES_BEFORE`, `COLLAPSE_BOUNDARY`,
`POSSIBILITIES_AFTER`, `LOST_POSSIBILITIES`, `CONSUMER`,
`CONSUMER_CAPABILITIES`, `COLLAPSE_REQUIRED`, `OBLIGATION_WITNESS`,
`STATIC_FREQUENCY`, `DYNAMIC_FREQUENCY`, `SIMPLE_FIX`, `COMPLEX_FIX`,
`SAFETY_RISK`, and `STATUS`) is preserved in
`POSSIBILITY_COLLAPSE_LEDGER_P8_2.json`.

The static audit found `TCMP->TBR3` in the tiny golden corpus, but no
`TREL->TBR3`, `TLOAD->TSTORE`, `TSTORE->TLOAD`, `TADDR->TREFLOAD`,
`TREFLOAD->TREFSTORE`, or `TMOV->TMOV` adjacency. This is triage, not a
whole-program frequency estimate.

## Collapse witnesses and counterexamples

The required/observed commitments are concrete: instruction-limit events,
initialization checks, bounds and immutable checks, failure behavior, calls and
ABI locations, address identity, alias observers, and successor liveness.
P8.1 also showed that broad metadata-removal candidates lack path-complete
proof. P5's SSA/phi and observer studies do not establish a general phi or
metadata-elision theorem. These are counterexamples to treating repeated
materialization as accidental merely because a later value looks redundant.

The strongest collapse is C2, but the strongest counterexample is its own
observer frontier: initialization metadata is semantically visible on paths
that are not represented by a simple local producer/consumer pair. Therefore
the safe classification remains `UNKNOWN`, not `READY_FOR_IMPLEMENTATION`.

## Decision

`P8_SELECTION=NO_VALID_TARGET_YET`

No production compiler change is justified. The next bounded experiment is a
path-complete observer-aware attribution of initialization and memory-state
materialization, separately classifying semantic memory, alias observation,
address-taken canonicalization, call synchronization, initialization state,
true spills, and unknown traffic. It must produce a falsifier and an exact
eligible population before any implementation branch is created.

P8.2 is a completed negative research result. P8 remains unimplemented, P9
was not started, and shutdown remains unauthorized.
