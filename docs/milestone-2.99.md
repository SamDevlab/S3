# Milestone 2.99: Bootstrap Promotion Readiness

M2.99 adds the final pre-M3.00 readiness decision for the bounded bootstrap
chain.

## Contract

- a valid reproducibility seal yields `candidate_ready=true`;
- the target remains explicit and unsupported targets fail closed;
- `production_promotion=false` remains mandatory;
- `full_self_hosting_claim=false` remains mandatory;
- the S3 candidate computes the same decision identity.

Readiness is a decision boundary, not an execution or release operation.

## Non-claims

M2.99 does not execute bootstrap, load source, invoke filesystem/network
services, invoke an assembler/linker, or promote production. Global T4 and
benchmarks remain reserved for M3.00.
