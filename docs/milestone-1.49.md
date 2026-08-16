# Milestone 1.49 - Portable WASI Host and Target Contract

Status: IMPLEMENTATION_COMPLETE_WITH_DEFERRED_ENVIRONMENT_CERTIFICATION.

## Delivered contract

M1.49 defines the bounded internal target `wasm32-wasip1-s3` and its
structural artifact contract. The implementation provides:

- a target identity distinct from native targets;
- a closed `wasi_snapshot_preview1` import manifest with capability mapping;
- explicit forbidden and unsupported import rejection;
- bounded 64 MiB linear memory and a logical instruction limit;
- deterministic core-module section ordering and fixture encoding;
- canonical artifact identity from source, lockfile, target, profile, compiler,
  and encoder inputs only;
- explicit separation between structural artifact construction and runtime
  execution.

The contract does not implement the Component Model, WASI Preview 2, browser
execution, or a second WASI generation. The normative target specification is
in [`spec/wasi-target.md`](../spec/wasi-target.md) and ADR-0036.

## Verification

- structural M1.49 tests: PASS (6);
- target/regression tests with `tests/test_target_spec.py` and
  `tests/test_m146_test_runner.py`: PASS (18);
- deterministic fixture bytes, canonical section order, import closure,
  identity locking, and no-runtime-claim checks: PASS;
- compileall: PASS;
- diff check: PASS;
- full suite on exact candidate
  `26c6cbb35e12c69f54840c43761162c506a8681b`: terminal exit 0;
- Wasmtime/wasm-tools runtime execution and Linux WASI certification:
  DEFERRED; neither toolchain is available in the approved environments.

The deferred runtime gates are environmental evidence gaps, not simulated
runtime results. No benchmark, remote write, CI trigger, Docker/virtualization
change, or shutdown action was performed.

## Boundary

The target and artifact identity contract is closed for this milestone.
Runtime execution remains a separate environment-certification gate and must
not be inferred from the structural fixture tests.
