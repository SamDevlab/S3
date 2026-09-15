# S3 1.1 R2 — Deterministic generation

Date: 2026-09-15

## Scope

R2 adds deterministic, grammar-aware single-source generation for Reliability Lab v2 on top of the merged R0/R1 contracts.

The implementation intentionally does not widen compiler semantics and does not import the historical Reliability Lab PR wholesale.

## Implemented

- fully specified SplitMix64 PRNG independent of Python `random` and `PYTHONHASHSEED`;
- R0 `derive_case_seed(...)` and `make_case_id(...)` identities;
- valid, malformed and mutated case kinds;
- exact UTF-8 source bytes with SHA-256 and byte counts;
- deterministic worker-request transport;
- explicit family/feature coverage accounting;
- source-size and campaign-count bounds inherited from the frozen R0 resource policy.

Valid families:

```text
scalar-call
i64-loop
trit-match
static-array
record
enum
mutable-reference
f64
```

Required valid feature coverage:

```text
aggregate.enum
aggregate.record
array.static
control.match
control.while
function.call
numeric.f64
numeric.i64
numeric.tryte
reference.mutable
```

Malformed families:

```text
lex-invalid-character
parse-missing-colon
parse-unclosed-expression
semantic-unknown-name
semantic-trit-range
semantic-unknown-function
```

Mutations are bounded and deterministic and are designed to force rejection by changing only source syntax.

## Deterministic vector audit

The frozen R2 vectors were independently recomputed from the specified algorithms:

```text
campaign_id=r2-vector
campaign_seed=123
case_index=0
case_kind=valid
case_seed=433001260938302787
source_sha256=85fdf536a55991b54a785f036c7f73515988296145af3cdc929963c2f1645341
case_id=144a15ee9606fb32507226241b2dbb0900324dacb3664516b694c2eb92ae2f32
```

Mutation vector:

```text
case_kind=mutated
case_seed=2797293811038360610
mutation=replace-first-arrow
source_sha256=4c65380db66dc27ef227366bf9ba886076ebba506ef51bd3d9616a02f2c29b4e
```

Algorithmic audit also confirmed:

```text
FROZEN_VECTOR_MATCH=YES
MUTATION_VECTOR_MATCH=YES
REQUIRED_VALID_FEATURE_COVERAGE=COMPLETE
MALFORMED_FAMILY_CYCLE=COMPLETE
MUTATIONS_DECLARED_REJECTION=YES
HOST_TIME_PID_RANDOM_DEPENDENCY=NO
```

## Syntax provenance audit

The valid families use syntax already present in the stable line rather than introducing generator-only grammar. Representative repository evidence includes:

- static arrays using `tryte[4] = [...]`;
- nominal records constructed with named fields;
- enum payload construction and payload `match` patterns;
- mutable references using `&mut` and dereference assignment;
- checked `i64`, IEEE-754 `f64`, loops and relational comparisons documented in the 1.0 line.

## Focused tests checked in

`tests/test_reliability_generator_v2.py` covers:

- frozen vectors;
- byte-identical repeatability;
- `PYTHONHASHSEED` independence;
- required feature coverage;
- malformed-family coverage;
- mutation bounds;
- metadata nondeterminism exclusions;
- worker-request byte preservation;
- sorted explicit coverage summaries;
- campaign fail-closed bounds;
- compile/rejection integration for every generated family.

## Execution boundary

The current ChatGPT runtime does not have the private repository mounted, and GitHub Actions runner provisioning remains blocked under issue #284. Therefore the real `compile_source(...)` integration parametrizations in the checked-in test file are **not claimed executed in this environment**.

This is recorded as infrastructure evidence debt, not converted into a fabricated PASS.

The deterministic identity/generation portion is closed by direct algorithmic reproduction and repository syntax audit. Compiler integration remains covered by executable tests and must be exercised as soon as a repository-capable runner is available.

## Status

```text
R2_DETERMINISTIC_IDENTITY=PASS
R2_VALID_GENERATION=IMPLEMENTED
R2_MALFORMED_GENERATION=IMPLEMENTED
R2_MUTATION=IMPLEMENTED
R2_SOURCE_HASH_METADATA=PASS
R2_COVERAGE_ACCOUNTING=PASS
R2_COMPILER_INTEGRATION_TESTS=CHECKED_IN
R2_COMPILER_INTEGRATION_EXECUTION=DEFERRED_RUNNER_UNAVAILABLE
R2_PRODUCTION_COMPILER_DELTA=NONE
R2_READY_FOR_R3_DESIGN=YES
```

R3 may start from this merged generation contract, but differential result claims still require actual worker execution; no hosted/native campaign result may be inferred from R2 alone.
