# M1.90 Architecture

M1.90 packages a local release candidate from deterministic source and target
artifact bytes and emits a target certification matrix alongside it. The
candidate includes target identity, artifact SHA-256, compiler commit, and
environment status. The matrix distinguishes structural proof from native
execution proof; unavailable Linux ARM64 and macOS ARM64 environments are
recorded as deferments rather than inferred passes.

The builder is intentionally local-only. It has no publish, upload, tag,
release, or remote-write operation. The resulting bundle can be verified by
the existing deterministic toolchain distribution verifier and is suitable for
the final campaign evidence directory.
