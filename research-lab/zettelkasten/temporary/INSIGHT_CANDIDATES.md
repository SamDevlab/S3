# S3 Zettelkasten — Temporary Insight Candidates

```text
DATE=2026-08-15
STATUS=ACTIVE
OFFICIAL_ZETTEL_IDS_ALLOCATED=NO
CANDIDATE_COUNT=8
```

These are second-order syntheses produced by connecting existing supported and open notes after the P13.R0 literature rebase.

They are intentionally **temporary**. Plausibility and explanatory power are not enough for permanent promotion.

Do not cite `IC-*` identifiers as established S3 facts.

## IC-001 — Optimization needs three gates: legality, realizability, profitability

Synthesis:

```text
LEGALITY
Can semantics be preserved?
    ↓
REALIZABILITY
Does the candidate map to a unique, actual compiler/physical effect?
    ↓
PROFITABILITY
Does that realized effect improve the target objective?
```

Connections:

```text
[[S3-ZK-0054]]
[[S3-ZK-0057]]
[[S3-ZK-0061]]
[[S3-ZK-0070]]
[[S3-ZK-0074]]
```

Why temporary:

The two-gate safety/profitability distinction is supported; elevating realizability into a general independent compiler gate is a new S3 synthesis that should be tested against future campaigns.

Candidate experiment:

Require the next optimization campaign to classify each candidate at all three gates and determine whether the extra gate prevents a false promotion or duplicate opportunity estimate.

---

## IC-002 — `UNKNOWN` is typed uncertainty

Synthesis:

```text
CORRECTNESS_UNKNOWN
→ fail closed / preserve behavior

PROFITABILITY_UNKNOWN
→ measure / model / benchmark

DIAGNOSTIC_UNKNOWN
→ classify / collect evidence
```

Connections:

```text
[[S3-ZK-0060]]
[[S3-ZK-0063]]
[[S3-ZK-0065]]
[[S3-ZK-0068]]
[[S3-ZK-0072]]
```

Why temporary:

The component rules are supported, but a compiler-wide uncertainty taxonomy has not yet been audited against active O1 state.

Candidate experiment:

P13.2 should inventory `UNKNOWN`-like states and classify whether each is semantic, profitability or diagnostic uncertainty.

---

## IC-003 — Proof facts require semantic ownership

Synthesis:

```text
A FACT WITHOUT STABLE SEMANTIC OWNERSHIP
IS NOT A TRANSPORTABLE PROOF.
```

A proof-bearing fact may need:

```text
FACT_ID
SEMANTIC_VALUE_OR_SITE_ID
PROPERTY
DERIVED_BY
VALID_REGION
DEPENDENCIES
INVALIDATORS
```

Connections:

```text
[[S3-ZK-0022]]
[[S3-ZK-0065]]
[[S3-ZK-0069]]
[[S3-ZK-0075]]
```

Why temporary:

Correction A proves that incidental object identity is invalid for semantic identity in the relevant compiler state. It does not yet prove S3 needs a general proof-object ownership system.

Candidate experiment:

P13.2 should trace a small set of proof-bearing facts across SSA reconstruction and record whether they are transferred, recomputed, invalidated or accidentally retained.

---

## IC-004 — Lowering boundaries should preserve a minimal proof interface

Synthesis:

A lowering boundary should not preserve maximal source structure merely for optionality. It should explicitly classify downstream-relevant facts as:

```text
PRESERVED
RECOMPUTABLE
INVALIDATED
INTENTIONALLY_DISCARDED
```

Connections:

```text
[[S3-ZK-0009]]
[[S3-ZK-0022]]
[[S3-ZK-0027]]
[[S3-ZK-0065]]
[[S3-ZK-0069]]
```

Why temporary:

The need to preserve required information is supported, but the proposed minimal proof-interface architecture has not been shown necessary or cost-effective for current S3.

Candidate experiment:

Build one boundary recoverability table in P13.2 before designing new metadata.

---

## IC-005 — Representation flexibility needs an explicit commitment boundary

Synthesis:

```text
DELAY IRREVERSIBLE REPRESENTATION CHOICES
UNTIL A JUSTIFYING CONSTRAINT EXISTS,
BUT DO NOT MAXIMIZE OPTIONALITY FOREVER.
```

Possible commitment evidence:

```text
SEMANTIC_REQUIREMENT
ABI_REQUIREMENT
RESOURCE_CONSTRAINT
TARGET_ARCHITECTURE_REQUIREMENT
MEASURED_PROFITABILITY_DECISION
```

Connections:

```text
[[S3-ZK-0009]]
[[S3-ZK-0016]]
[[S3-ZK-0017]]
[[S3-ZK-0071]]
[[S3-ZK-0073]]
```

Why temporary:

This refines an older preservation philosophy but no general S3 commitment-boundary metric has been demonstrated.

Candidate experiment:

When P14 selects a target, identify the earliest irreversible representation commitment and test whether delaying it changes a unique realizable downstream effect.

---

## IC-006 — The optimizer pipeline can be audited as a proof-flow graph

Synthesis:

Pass ordering may be partially modeled through explicit relationships:

```text
PRODUCES
CONSUMES
PRESERVES
INVALIDATES
REQUIRES
```

rather than only by a sequential pass list.

Connections:

```text
[[S3-ZK-0022]]
[[S3-ZK-0065]]
[[S3-ZK-0067]]
[[S3-ZK-0069]]
[[S3-ZK-0075]]
```

Why temporary:

The existing `SSAPassContract` architecture may already encode enough of this information, or the added structure may not justify its complexity.

Candidate experiment:

P13.2 should map the existing pass contracts first. Add no new framework unless missing dependencies cause an observable correctness or invalidation gap.

---

## IC-007 — Negative results can become scoped exclusion constraints

Synthesis:

A closed negative-result note can actively constrain future target selection through:

```text
CLAIM
SCOPE
SHA_RANGE
CORPUS
ASSUMPTIONS
WHAT_WAS_FALSIFIED
WHAT_WAS_NOT_FALSIFIED
REOPEN_CONDITION
```

Connections:

```text
[[S3-ZK-0052]]
[[S3-ZK-0054]]
[[S3-ZK-0057]]
[[S3-ZK-0058]]
[[S3-ZK-0059]]
[[S3-ZK-0060]]
[[S3-ZK-0061]]
[[S3-ZK-0062]]
```

Why temporary:

The permanent index already adopts a reopen rule, but the full exclusion-constraint schema has not yet been applied retroactively to all negative notes.

Candidate experiment:

Before P14 target selection, require each candidate family to reconcile against existing scoped negative results.

---

## IC-008 — Separate semantic domain, legal representations and target realization

Synthesis:

```text
SEMANTIC DOMAIN
    ↓
LEGAL REPRESENTATION SET
    ↓
TARGET-SPECIFIC REALIZATION
```

For example:

```text
trit / tryte / i64 / f64 / reference / aggregate
        ↓
register / immediate / flags / frame / packed / canonical memory / ...
        ↓
x86-64 realization today
```

Candidate policy:

```text
SEMANTICS = LANGUAGE POLICY
LEGAL REPRESENTATIONS = COMPILER POLICY
PHYSICAL SELECTION = TARGET POLICY
```

Connections:

```text
[[S3-ZK-0016]]
[[S3-ZK-0017]]
[[S3-ZK-0067]]
[[S3-ZK-0073]]
```

Why temporary:

This is a promising synthesis for a multi-domain S3, but the compiler architecture has not yet been shown to require this explicit three-layer model.

Candidate experiment:

P13.0/P13.2 should map where semantic type, representation legality and target lowering are currently conflated versus explicitly separated.

## Promotion rule for insight candidates

An `IC-*` candidate may become a normal `S3-ZK-*` note only after it has:

```text
ATOMIC_CLAIM
SOURCE/NOTE PROVENANCE
CURRENT S3 EVIDENCE
SCOPE
FALSIFIER
BOUNDED VALIDATION PATH
```

Do not promote all eight automatically. Negative evidence may reject or merge candidates.
