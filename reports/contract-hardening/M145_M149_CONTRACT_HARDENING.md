# M1.45–M1.49 Contract Hardening

Status: `COMPLETE`.

The remaining audit gaps are now represented by versioned JSON contracts,
golden fixture definitions, and stable gate identifiers. No production code,
test code, architecture decision, or roadmap ordering was changed.

M1.45: canonical lockfile, artifact identity, hash domain, normalization,
foreign ABI identity, and reproducibility goldens are in the lockfile/artifact
schemas and `M145_GOLDENS.json`.

M1.46: `s3.test-report.v1` fixes statuses, exit codes, timeout bounds,
capability-denial distinction, and discovery ordering.

M1.47: the descriptor layout, Stable ABI symbol profile, and live-borrow
reallocation negative gate are explicit. Linux availability remains an
environment-only dependency.

M1.48: TCP error codes, bounded resource values, binary address encoding, and
versioned provider traces are explicit. Linux loopback remains deferrable.

M1.49: the Preview 1 import manifest, filesystem rights matrix, and runtime
certification profile are explicit. Wasmtime/wasm-tools remain environment
only; no tool versions are invented.

M1.50 was not changed.

Integration order: review M1.45 artifacts after its transaction boundary;
integrate M1.46–M1.48 before their own implementation milestones; retain M1.49
schemas as certification prerequisites. No executable tests were added.
