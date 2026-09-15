# F3 — package, clean-install and reproducibility gate

Date: 2026-09-14

Status: **PASS**.

The first PR-triggered Actions runs for this candidate did not obtain runners,
so they produced no repository-step evidence. The bounded local executable
gate below supplies the package evidence for this checkpoint.

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

The gate records archive identities and requires byte identity for the two
independent builds. The packaging command now normalizes the sdist release
tree and gzip/tar metadata when an explicit epoch is provided.

## Current static preparation

The candidate branch already contains:

- `pyproject.toml` distribution version `1.0.0`;
- synchronized deterministic WASM compiler identity `s3-bootstrap-1.0.0`;
- `tests/test_release_version_surfaces.py` preventing accidental syntax/IR/Assembly/diagnostic version drift;
- `docs/releases/1.0.0.md` marked DRAFT / NOT PUBLISHED;
- Apache-2.0 project license at `LICENSE`.

## Execution evidence

```text
F3_GATE_DEFINED=YES
F3_PYTHON=3.13.15
F3_SOURCE_DATE_EPOCH=1700000000
F3_WHEEL_BUILD=PASS
F3_SDIST_BUILD=PASS
F3_METADATA_VALIDATION=PASS
F3_CLEAN_VENV_INSTALL=PASS
F3_CLI_SMOKE=PASS
F3_EXAMPLE_SMOKE=PASS
F3_LICENSE_PACKAGE_INVENTORY=PASS
F3_WHEEL_BYTE_IDENTITY=PASS
F3_SDIST_BYTE_IDENTITY=PASS
F3_STATUS=PASS
```

The final independent builds were written to `dist-release-g` and
`dist-release-h` during the local gate. Both contained one wheel and one
sdist, with 161 wheel entries and 569 sdist entries. No unsafe or excluded
paths were present.

```text
WHEEL=s3_bootstrap-1.0.0-py3-none-any.whl
WHEEL_BYTES=437037
WHEEL_SHA256=3b8490c30a09eaa594920462f8c9c9e7267bc270e92ca79e635f593d2ee83d76
SDIST=s3_bootstrap-1.0.0.tar.gz
SDIST_BYTES=695713
SDIST_SHA256=f295a899d147f7170f4143fb5fa30b9c42b70db10a2d45d60f3a85a34c9f7ae8
WHEEL_AND_SDIST_BYTE_IDENTITY=PASS
```

The sdist reproducibility correction is in the packaging-only `setup.py`:
when `SOURCE_DATE_EPOCH` is supplied, release-tree metadata and the gzip/tar
headers use that epoch with normalized ownership. The clean installation
reported version `1.0.0`; `s3 --help`, both `check` smokes and the `run`
smoke all exited zero.
