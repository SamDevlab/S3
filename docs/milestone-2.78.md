# Milestone 2.78: Composed Semantic Closure

M2.78 composes the bounded semantic candidates from M2.71 through M2.77
behind one canonical input/output contract.

## Scope

The canonical input carries bounded symbol-table, lexical-scope,
scalar-type, place/reference, function-call, fixed-layout and control-flow
requests in fixed arrays. The S3 candidate is one composed program: the
previous S3 kernels are namespace-isolated and invoked by
`check_semantic_closure`. The adapter serializes raw canonical inputs and does
not compute semantic answers for the candidate.

The canonical output is either a stage-specific rejection code or a bounded
identity in the range `0..180`. Accepted identities fold the exact component
results and the four deterministic M2.76 layout identity lanes. This is a
deterministic contract, not a cryptographic fingerprint or a claim of global
semantic completeness.

## Evidence Contract

- S3 composition: `selfhost/semantic/semantic_closure_candidate.s3`.
- Python adapter and differential reference:
  `bootstrap/s3/semantic_closure_candidate.py`.
- Focused contract: `tests/test_m278_semantic_closure_candidate.py`.
- Component entrypoints: M2.71 symbol lookup, M2.72 name resolution, M2.73
  scalar checking, M2.74 place checking, M2.75 function calls, M2.76 record
  and enum layouts, and M2.77 control-flow analysis.
- Rejection stages are stable: symbols `201`, names `202`, scalar `203`,
  places `204`, functions `205`, layouts `206`, and flow `207`.

## Non-claims

M2.78 does not claim semantic candidate routing, complete language semantic
coverage, native self-hosting, production promotion, performance improvement
or full compiler self-hosting. Candidate routing is M2.79 work and the
semantic checkpoint is M2.80.
