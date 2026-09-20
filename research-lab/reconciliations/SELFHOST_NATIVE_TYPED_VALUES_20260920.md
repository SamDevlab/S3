# Native Typed Value Protocol Reconciliation

Date: 2026-09-20

## Provenance

```text
SOURCE_BASE_PR=305
SOURCE_BASE_HEAD=48f2551c130ba29e6becf63aba2d4e57c69d35c6
CAMPAIGN_BRANCH=feat/s3-native-typed-values
FUNCTIONAL_HEAD=cc05357ad6e72c3bc13032b1ed55303be93f2661
```

This was a new campaign branch based exactly on the open Draft PR305
documentation head. PR305 and the protected canonical source were not
modified.

## Evidence

The native scalar execution path now carries explicit typed identity through a
small `NativeTypedValue` / `NativeTypedResult` protocol. The selected model is
parallel type tag plus typed payload fields. It preserves the existing i64
path and the first real result remains `42`. A real f64 source fixture also
passes tokenization, local binding, assignment, parameter passing, function
call, return, and exact known-result comparison for `4.75`.

Mixed i64/f64 binary operations are rejected. No implicit promotion, dynamic
typing, hosted evaluator fallback, or fake native workload was introduced.

```text
NATIVE_TYPED_VALUE_PROTOCOL=PASS
NATIVE_I64_SEMANTIC_EXECUTION=PASS
I64_POST_TYPED_PROTOCOL_RESULT=42
NATIVE_F64_SCALAR_EXECUTION=PASS
NUMERIC_COERCION_POLICY=NONE
REFERENCE_FALLBACK=NONE
FULL_SUITE=4021 passed, 312 skipped, 0 failed
FULL_SUITE_EXIT=0
FULL_SUITE_HEAD=cc05357ad6e72c3bc13032b1ed55303be93f2661
```

The full suite was run once at the functional head on Windows. Compileall,
diff-check, focused semantic tests, and adjacent frontend/fixed-layout tests
passed. Linux qualification was not claimed because this execution host is
Windows.

## Boundary and decision

The hosted semantic model has fixed arrays and slices, but the native typed
protocol has no collection payload, element type, length, bounds, mutability,
or ownership/lifetime representation. Therefore native indexed execution is
not ready and the first missing capability is:

```text
NATIVE_INDEXED_VALUE_PAYLOAD_LENGTH_BOUNDS_OWNERSHIP_CONTRACT
```

This is a representation and ownership boundary, not a local f64 bug. The
next design decision is to define the smallest native fixed-array/slice
representation and its bounds/ownership protocol before adding index reads or
numeric/scientific workloads. No native numeric or scientific workload was
started.

## Knowledge reconciliation

This result strengthens IC-005, IC-008, IC-012, IC-015, and IC-016:

- representation flexibility must be preserved until native value identity is
  explicit;
- semantic domain, legal representation, and target realization remain
  distinct;
- a bounded semantic-layer replacement can generalize from i64 to f64 without
  becoming a dynamic runtime;
- useful workload requirements identify the next minimum capability;
- self-hosting remains an enabling milestone, not the terminal objective.

IC-014 is unchanged: all signatures in this slice remain explicitly typed and
no type inference was introduced. The negative result is that hosted indexed
data semantics do not automatically supply a native layout or ownership
contract.

The production report is:

`reports/s3-native-typed-values/FINAL_REPORT.md`

