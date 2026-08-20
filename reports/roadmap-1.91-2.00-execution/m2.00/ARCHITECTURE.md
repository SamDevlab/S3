# M2.00 Architecture: Release Candidate Stability Gate

The M2.00 gate composes the existing local toolchain bundle and release
candidate validators with an exact three-target compatibility scope. It binds
the candidate version and compiler commit into bundle metadata, verifies the
LICENSE digest, compares repeated bundle bytes, and verifies a provenance
envelope through the existing vetted signature-provider boundary.

The gate is local-only. It does not publish, tag, or release artifacts. Native
target status is preserved per target; unavailable ARM environments remain
`DEFERRED_BY_ENVIRONMENT`.
