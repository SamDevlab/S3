# S3-ZK-0073 — Profitability is target-architecture dependent

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

The most profitable legal transformation can depend on the target machine; a machine-independent structural improvement is not sufficient evidence for native runtime profitability.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

### Source claim

Allen & Kennedy shows that legal loop transformations can have different profitability on different architectures and states that target architecture is often the principal factor in selecting the most profitable loop-interchange pattern. Cooper & Torczon likewise treats scheduling, register allocation and code generation as target-sensitive interacting backend problems.

### S3 inference

S3 should preserve machine-independent semantics and correctness as long as possible, while allowing target-aware profitability decisions late enough to use real target constraints.

For the current native path:

```text
TARGET=x86-64 Linux
```

P14 runtime conclusions must be measured on the actual target environment used by the experiment.

A future ternary backend, ARM backend, or other target could legitimately make different profitability choices while preserving the same source semantics.

## S3 implication

Do not promote a transformation because it:

```text
reduces IR
reduces abstract operations
reduces static instruction count
```

without establishing the intended target-level objective.

This supports a multi-domain language design: semantic domains need not dictate a single physical representation or target strategy.

## Connections

```text
[[S3-ZK-0016]] --semantic-before-encoding--> [[S3-ZK-0073]]
[[S3-ZK-0068]] --supports--> [[S3-ZK-0073]]
[[S3-ZK-0070]] --governs--> [[S3-ZK-0073]]
```

## Falsifier / narrowing condition

Some transformations may be profitable across all supported targets for a particular objective. Such universality must be demonstrated; it cannot be assumed from legality or structural simplification alone.

## Experiment

P14 should record exact target/toolchain/machine fingerprint with every runtime result. Future multi-target work should compare profitability decisions without changing semantic correctness gates.

## Evidence

Source-derived architecture dependence plus P12.17 S3 evidence that structural dynamic reduction did not predict x86-64 runtime benefit.

## Decision

```text
SUPPORTED
```