# M1.56 Package Identity Fix

Base: `76030c5d5428e47f6839c219c4930db4cb1862d8`

Fix commit: `cf5f8f925853ebbba34866296816d9f254b549e8`

`PackageLock.resolve` now records dependency declarations only while walking
the selected root graph. Every reachable non-root package must have one
canonical `(source, revision)` identity. Conflicting reachable references
raise `PackageDependencyError` with a deterministic package-specific message.
The root remains `source="."`, `revision=None`. Unreachable manifests do not
participate in resolution.

Focused certification:

- conflicting source rejected: PASS
- conflicting revision rejected: PASS
- identical multi-parent reference accepted: PASS
- mapping order independent: PASS
- unreachable reference ignored: PASS
- lock text and SHA deterministic: PASS
- `tests/test_m156_package_dependencies.py`: PASS
- T2 M1.56: 3 files passed
