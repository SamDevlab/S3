# Milestone 2.82: Canonical Expression Lowering

M2.82 lowers a bounded post-order expression tree into the canonical IR data
model introduced by M2.81. The experiment is isolated from the production
compiler lowering path and remains hosted, explicit and fail-closed.

## Contract

- the input contains at most three post-order nodes;
- supported nodes are literal, add, numeric difference and multiply;
- binary nodes may reference only earlier nodes;
- each node receives its stable result register and the generated function
  ends with an explicit `RETURN` of the selected root;
- the Python reference and S3 candidate compare the same canonical IR
  identity.

## Non-claims

M2.82 does not replace production lowering, cover calls or aggregates, verify
CFG/type correctness, select a candidate by default, claim native execution,
claim performance improvement or run global T4. Call and aggregate lowering
are M2.83 work and verifier work is M2.84 work.
