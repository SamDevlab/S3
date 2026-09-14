# F1 — version surface inventory and stable-release decision

Date: 2026-09-14

## Inventory at stabilization start

The current canonical repository exposes several intentionally independent version surfaces.

| Surface | Canonical value before candidate prep | Stable 1.0 decision |
|---|---:|---:|
| GitHub stable release | `v0.7.0` | prepare `v1.0.0`, do not publish yet |
| GitHub prerelease | `v1.0.0-rc2` | predecessor candidate |
| Python distribution `s3-bootstrap` | `0.7.0` | `1.0.0` |
| source syntax default | `0.6` | unchanged |
| IR JSON | `0.6.0` | unchanged |
| S3 Assembly | `0.6.0` | unchanged |
| `s3-diagnostic` schema | `1.0.0` | unchanged |
| AI capability manifest schema | `1.0.0` | unchanged |
| WASM structural encoder profile | `s3-wasm-encoder-v1` | unchanged |

Authoritative implementation evidence for the preserved language/artifact surfaces:

```text
SyntaxMode default = V0_6
IR_FORMAT_VERSION = 0.6.0
ASSEMBLY_FORMAT_VERSION = 0.6.0
DIAGNOSTIC_SCHEMA_VERSION = 1.0.0
```

## Distribution-version decision

The stable publication candidate uses:

```text
DISTRIBUTION_NAME=s3-bootstrap
DISTRIBUTION_VERSION=1.0.0
```

This is a release/package identity change, not a semantic format bump.

The candidate branch therefore changes `pyproject.toml` from `0.7.0` to `1.0.0`.

## Compiler identity synchronization

`bootstrap/s3/wasm_target.py` includes the compiler identity in deterministic WASM artifact identity calculation. Before this campaign its default was:

```text
s3-bootstrap-0.7.0
```

Leaving that value unchanged while publishing a `1.0.0` distribution would create two contradictory compiler-version identities. The candidate branch therefore aligns it to:

```text
s3-bootstrap-1.0.0
```

This intentionally changes artifact identity for otherwise-equal WASM structural inputs under the new compiler version; the encoded module bytes and encoder profile remain unchanged.

## Regression lock

`tests/test_release_version_surfaces.py` was added to prove two properties:

1. package metadata and the WASM compiler identity remain synchronized;
2. the stable package-version bump does not silently change source syntax, IR, Assembly or diagnostic schema contracts.

The test is release-surface evidence only. It does not replace the normal focused, packaging or final certification gates.

## Release notes

A draft stable note now exists at:

`docs/releases/1.0.0.md`

It is explicitly marked `DRAFT / NOT PUBLISHED` and records the publication boundary.

## F1 decision

```text
F1_VERSION_INVENTORY=PASS
F1_DISTRIBUTION_VERSION_DECISION=1.0.0
F1_LANGUAGE_VERSION_BUMP=NO
F1_IR_VERSION_BUMP=NO
F1_ASSEMBLY_VERSION_BUMP=NO
F1_DIAGNOSTIC_SCHEMA_BUMP=NO
F1_WASM_COMPILER_IDENTITY_SYNC=YES
F1_RELEASE_NOTES_PREPARED=YES
TAG_CREATED=NO
GITHUB_RELEASE_CREATED=NO
PACKAGE_REGISTRY_PUBLISHED=NO
```

F1 is complete as a source decision. The new candidate metadata still requires CI/focused validation and later packaging/install/reproducibility evidence before candidate freeze.
