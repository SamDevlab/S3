# S3-ZK-0001 — Preserve location flexibility before physical allocation

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-12
```

## Atomic claim

A logical scalar value should not acquire mandatory frame identity before a semantic/resource constraint proves that memory is required.

## Origin

```text
SOURCE_DERIVED + S3_MEASURED
```

Compiler literature motivates keeping live values consistently available across block boundaries rather than always storing/reloading them. P1–P3 S3 evidence shows that late emitter forwarding removes only a small portion of the global frame traffic.

## S3 implication

Represent independently:

```text
logical identity
location flexibility
memory validity
physical register assignment
```

Do not make `logical value == frame slot` an accidental invariant.

## Connections

```text
[[S3-ZK-0001]] --supports--> [[S3-ZK-0002]]
[[S3-ZK-0001]] --supports--> [[S3-ZK-0009]]
[[S3-ZK-0006]] --motivates--> [[S3-ZK-0001]]
```

## Falsifier

If tracing proves frame identity is already semantically required for essentially all dynamically relevant values, this claim becomes much narrower.

## Experiment

Trace at least 50 logical values from SSA/Assembly IR to native locations and record the first point where location flexibility is lost.
