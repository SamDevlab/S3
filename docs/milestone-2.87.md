# Milestone 2.87: Lowering Checkpoint

M2.87 records a bounded checkpoint joining the qualified expression lowering,
call/aggregate lowering and canonical IR verifier contracts. It is an
experimental hosted composition and does not change production lowering.

## Contract

- expression and call identities come from their existing reference producers;
- verifier acceptance and rejection stage remain visible;
- the S3 candidate receives only the qualified scalar contract values;
- the checkpoint identity is deterministic and bounded;
- invalid IR remains a verifier result rather than being hidden by lowering.

## Non-claims

M2.87 does not add production lowering, alter public IR 0.6.0, enable a default
candidate path, claim native self-hosting, claim performance improvement or
run global T4. A broader composed lowering closure is a later milestone.
