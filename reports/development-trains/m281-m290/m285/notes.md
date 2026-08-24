# M2.85 hardening evidence

The Python model is the reference lowering. The S3 candidate is
`selfhost/lowering/control_flow_aggregate_candidate.s3`-equivalent generated
lane source in the bounded candidate harness; each block/instruction field is
queried through an S3 function and reconstructed by Python. The differential
compares canonical structures and canonical bytes, not a fingerprint.

M2.84 real interop is PASS for a representable single-block linear fixture via
`run_ir_verifier_differential`. Multi-block IF/ELSE/loop fixtures are not
claimed as M2.84-verified because the current verifier is single-block/linear;
multi-block verifier closure is deferred to M2.88.

M2.83 reuse is limited to ordered call/aggregate-result placement; this is not
full aggregate closure.
