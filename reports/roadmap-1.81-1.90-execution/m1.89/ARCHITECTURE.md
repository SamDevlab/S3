# M1.89 Architecture

M1.89 closes the macOS ARM64 target artifact path using the existing shared
AArch64 instruction contract and the Mach-O 64-bit ARM64 header contract. The
target identity, assembly body, container identity, and native execution
certificate are distinct fields in the integration result.

The current host is Windows, so macOS ARM64 execution is not attempted and is
reported as `DEFERRED_BY_ENVIRONMENT`. Structural Mach-O validation is not
reclassified as Apple Silicon execution evidence.
