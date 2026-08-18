# M1.80 - Reproducible Toolchain Distribution V1 Architecture

## MILESTONE

`M1.80 REPRODUCIBLE_TOOLCHAIN_DISTRIBUTION_V1`

## PROBLEM

S3 needs a local, reviewable toolchain bundle that can be rebuilt identically
without embedding machine paths or silently creating a release.

## PUBLIC_SURFACE

`ToolchainBundler` accepts logical source files, a license, and stable metadata
and emits a deterministic ZIP bundle containing `MANIFEST.json`, `LICENSE`,
files, and checksums. `ToolchainBundle` exposes bytes and SHA-256.

## OWNERSHIP_MODEL

Bundle inputs are copied as immutable bytes under validated logical names. The
builder does not retain source filesystem handles or execute bundled code.

## RESOURCE_MODEL

Input count, path length, and bundle size are bounded. Every bundle includes a
license and manifest before it is accepted.

## FAILURE_MODEL

Unsafe paths, duplicate logical names, missing license, unstable metadata,
checksum mismatch, and malformed bundle are explicit `DistributionError`
values. No remote release operation exists.

## LOWERING_MODEL

The distribution format serializes existing compiler/toolchain artifacts; it
does not change language or backend lowering.

## DETERMINISM_MODEL

File names are sorted, ZIP timestamps/attributes are fixed, JSON is canonical,
and no current directory, hostname, user, or wall-clock data is recorded.

## PLATFORM_MODEL

The bundle format is platform-neutral. A target-specific execution certificate
is metadata supplied by a separate environment gate, never inferred from a
bundle build on Windows.

## OUT_OF_SCOPE

Signing, update channels, remote release, package publishing, installer
creation, and machine-specific binary certification.

## TEST_STRATEGY

Focused tests cover repeat builds, manifest/checksum/license presence,
machine-path rejection, metadata determinism, corrupted bundle detection, and
the absence of a release operation.
