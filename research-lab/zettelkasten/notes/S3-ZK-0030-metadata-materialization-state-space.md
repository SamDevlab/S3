# S3-ZK-0030 — Memory-state metadata is a distinct optimization state space

TYPE: HYPOTHESIS
STATUS: SUPPORTED_BY_P4_RESIDUAL

## Thesis

Ordinary logical-value residency and compiler/runtime memory-state metadata should be modeled and attributed separately.

Optimizing scalar value placement can leave metadata materialization untouched even when both appear as frame/memory traffic in final code.

## P4 evidence

Direct probe:

```text
TOTAL_FRAME_ACCESSES: 9282 -> 7175
METADATA_ACCESSES:     5638 -> 5638
```

P4 therefore removed a large amount of value-related frame traffic while metadata traffic remained unchanged.

Residual diagnosis:

```text
REPEATED_MEMORY_STATE_MATERIALIZATION
```

## Research implication

The next causal model should distinguish at least:

```text
VALUE_STATE
MEMORY_VALIDITY_STATE
INITIALIZATION_STATE
SSA_MERGE_STATE
ABI/OBSERVABILITY_STATE
```

Potential connections include:

- reduced-product abstract domains;
- explicit bounded proof/fact objects;
- memory versions;
- SSA destruction metadata;
- finite-state minimization where state is purely compiler metadata.

Do not assume the correct solution is another register-allocation change.

## Connections

- [[S3-ZK-0004]] reduced product domains
- [[S3-ZK-0009]] information loss
- [[S3-ZK-0022]] proof/fact preservation
- [[S3-ZK-0025]] bounded fact language
- [[S3-ZK-0027]] information-lossless lowering
- [[S3-ZK-0029]] causal metric hierarchy

## Falsifier

If per-origin attribution proves the 5638 metadata accesses are semantically/ABI mandatory or are not materially repeated state realization, this hypothesis must be narrowed or rejected.

## Source

Production P4 / PR #170, reconciled in `research-lab/reconciliations/P4_20260812.md`.
