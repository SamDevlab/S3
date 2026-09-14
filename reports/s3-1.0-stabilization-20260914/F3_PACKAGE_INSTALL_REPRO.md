# F3 — package, clean-install and reproducibility gate

Date: 2026-09-14

Status: **PREPARED / EXECUTION EVIDENCE PENDING**.

F3 is intentionally not marked PASS until an executable environment completes the package gate. The first PR-triggered Actions runs for this candidate did not obtain runners, so they produced no repository-step evidence.

## Candidate package contract

```text
DISTRIBUTION=s3-bootstrap
CANDIDATE_VERSION=1.0.0
SOURCE_SYNTAX=0.6
IR_FORMAT=0.6.0
ASSEMBLY_FORMAT=0.6.0
DIAGNOSTIC_SCHEMA=1.0.0
```

## Dedicated gate

`.github/workflows/release-candidate.yml` defines a bounded `package-gate` that performs the following on Python 3.13:

1. installs release build tooling without changing project runtime dependencies;
2. builds one wheel and one sdist twice with a fixed `SOURCE_DATE_EPOCH`;
3. validates wheel/sdist package name and version metadata;
4. verifies LICENSE presence in both distributions and README presence in the sdist;
5. creates a clean virtual environment;
6. installs the built wheel, not an editable checkout;
7. verifies installed metadata reports `s3-bootstrap 1.0.0`;
8. runs `s3 --help`;
9. runs bounded official-example smoke checks;
10. records SHA-256 values and byte-identity observations for the two independent builds.

The gate deliberately prints archive identity comparison rather than pretending byte identity before the actual build system proves it. If the repository's stable reproducibility contract requires byte identity and the two builds differ, the candidate remains blocked until the difference is classified and repaired or the contract is clarified without weakening existing guarantees.

## Current static preparation

The candidate branch already contains:

- `pyproject.toml` distribution version `1.0.0`;
- synchronized deterministic WASM compiler identity `s3-bootstrap-1.0.0`;
- `tests/test_release_version_surfaces.py` preventing accidental syntax/IR/Assembly/diagnostic version drift;
- `docs/releases/1.0.0.md` marked DRAFT / NOT PUBLISHED;
- Apache-2.0 project license at `LICENSE`.

## Execution status

```text
F3_GATE_DEFINED=YES
F3_WHEEL_BUILD=NOT_YET_OBTAINED
F3_SDIST_BUILD=NOT_YET_OBTAINED
F3_METADATA_VALIDATION=NOT_YET_OBTAINED
F3_CLEAN_VENV_INSTALL=NOT_YET_OBTAINED
F3_CLI_SMOKE=NOT_YET_OBTAINED
F3_EXAMPLE_SMOKE=NOT_YET_OBTAINED
F3_REBUILD_IDENTITY_OBSERVATION=NOT_YET_OBTAINED
F3_LICENSE_PACKAGE_INVENTORY=NOT_YET_OBTAINED
F3_STATUS=OPEN_PENDING_EXECUTABLE_RUNNER
```

F3 cannot be closed from documentation or source inspection alone.
