# Research Prototypes

These modules are **pre-production research code**. They intentionally avoid dependencies on S3 production IR so mathematical ideas can be tested in isolation first.

They are not compiler passes and must not be imported by production S3 code.

## Current prototypes

```text
cfg.py
    Tiny generic CFG/value model.

liveness.py
    Backward fixed-point live-in/live-out analysis.

residence_lattice.py
    Small representation-knowledge domain and join/transfer helpers.

materialization_cut.py
    Self-contained max-flow/min-cut solver for a binary
    flexible-vs-memory materialization-placement experiment.

exact_oracle.py
    Exhaustive binary-assignment oracle for tiny placement problems.

demo.py
    Cross-checks min-cut against exhaustive enumeration and exercises liveness.
```

## Run

From repository root:

```bash
python research-lab/prototypes/demo.py
```

The demo should terminate with:

```text
OK
```

## Research progression

1. Keep the model generic.
2. Establish mathematical validity/counterexamples.
3. Add S3 trace adapters **outside production code**.
4. Compare model predictions against actual S3 Assembly IR/native frame traffic.
5. Only then design a production implementation.

## Important limitation

The binary cut prototype optimizes **one value or independent values without shared register-capacity coupling**. It is not evidence that general register allocation is a min-cut problem.
