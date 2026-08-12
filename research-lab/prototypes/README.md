# Research Prototypes

These modules are **pre-production research code**. Most intentionally avoid dependencies on S3 production IR so mathematical ideas can be tested in isolation first. Files explicitly named as adapters/traces may import S3 code, but production S3 must never import the research lab.

They are not compiler passes.

## Current prototypes

```text
cfg.py
    Tiny generic CFG/value model.

liveness.py
    Backward fixed-point live-in/live-out analysis.

residence_lattice.py
    Small finite powerset representation-knowledge domain,
    lattice-law checks, and monotone transfer prototypes.

materialization_cut.py
    Self-contained Dinic max-flow/min-cut solver for a binary
    flexible-vs-memory materialization-placement experiment.

exact_oracle.py
    Exhaustive binary-assignment oracle for tiny one-value placement problems.

lagrangian_capacity.py
    Multi-value shared-capacity relaxation. Per-point register scarcity receives
    an integer price so fixed-price subproblems decompose into independent cuts.

multivalue_oracle.py
    Exhaustive exact oracle for tiny multi-value placement with shared capacity.

combinatorial_checks.py
    Exhaustive matroid hereditary/exchange counterexample finder and
    submodularity checker for tiny value sets.

s3_adapter.py
    Research-only projection from current S3 AssemblyFunction to the generic
    CFG plus a liveness cross-check bridge.

value_trace.py
    Research-only Assembly/allocator value corpus scaffold that records
    defs/uses/live-out/address-taking/call crossing/current allocation and
    explicitly marks where earlier-layer attribution is still unknown.

trace_cli.py
    CLI scaffold for emitting liveness/value traces from textual S3 Assembly.

demo.py
    Exercises lattice laws, liveness, min-cut vs exact oracle, and
    combinatorial counterexample tools.

capacity_demo.py
    Exercises the exact multi-value oracle and weak-duality behavior of the
    first Lagrangian capacity relaxation on a deliberately symmetric case.
```

## Run generic self-checks

From repository root:

```bash
python research-lab/prototypes/demo.py
python research-lab/prototypes/capacity_demo.py
```

Expected endings include:

```text
residence_lattice=PASS
liveness=PASS
mincut_vs_exact_oracle=PASS
matroid_counterexample_tool=PASS
submodularity_counterexample_tool=PASS
OK
```

and:

```text
multi_value_exact_oracle=PASS
lagrangian_weak_duality=PASS
lagrangian_exact_dual_bound_on_symmetric_case=PASS
OK
```

## S3 trace bridge

Given a text file accepted by `bootstrap.s3.assembly.parse_assembly`:

```bash
python research-lab/prototypes/trace_cli.py path/to/assembly.txt
```

The trace CLI is research scaffolding; exact input generation/integration with the established jsmn harness remains an experiment task.

## Research progression

1. Keep mathematical models generic where practical.
2. Establish validity or minimal counterexamples.
3. Use S3 adapters only as a bridge from real compiler evidence.
4. Cross-check research liveness against current production liveness before trusting novel analyses.
5. Compare model predictions against actual S3 Assembly IR/native frame traffic.
6. Extend tracing earlier in the pipeline until the **first location-flexibility loss** is factually identified.
7. Only then design a production implementation.

## Important limitations

The binary cut prototype optimizes **one value or independent values without shared register-capacity coupling**. It is not evidence that general register allocation is a min-cut problem.

The Lagrangian prototype adds only a simplified per-point capacity coupling. Real interference, register classes, ABI constraints and identity/coalescing may require a richer model. A tight dual bound also does not guarantee the independently chosen primal placements are feasible or optimal.

The exact oracles and combinatorial checks are intentionally exponential and bounded to tiny research inputs.

`value_trace.py` starts at `AssemblyFunction`; it therefore cannot by itself prove that a stack-resident value is a true RA spill. Earlier IR/frame evidence remains necessary.
