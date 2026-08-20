# M1.90 Architecture

M1.90 builds deterministic local release-candidate bundles and an explicit target certification matrix. Structural and native execution evidence remain separate fields; Linux AArch64/macOS ARM64 native execution can remain deferred without being converted into structural or execution success.

A target is no longer marked `STRUCTURAL_PASS` merely because arbitrary bytes were supplied. Every target artifact requires a registered structural validator and must pass it before the certificate is emitted. Built-in Linux AArch64 validation checks ELF64/AArch64 identity; built-in macOS ARM64 validation checks Mach-O 64/ARM64 identity. Unknown targets require an explicit validator rather than receiving an automatic pass.

The RC bundle requires actual Apache-2.0 license text; there is no placeholder default LICENSE. Bundle metadata records `license=Apache-2.0`, and the deterministic toolchain bundle verifier is run before the candidate is returned. The verifier is fail closed: raw and canonical member names must be unique; every member must be a canonical regular stored file; archive member count and total uncompressed bytes are bounded; archive membership must exactly equal `MANIFEST.json` plus `LICENSE`; manifest file records are unique, canonical, bounded, and schema-checked; the embedded manifest must equal the in-memory manifest and use canonical serialization; and `LICENSE` size/hash are bound into the manifest. Unmanifested extras, duplicate ZIP names, canonical path collisions, malformed manifests, checksum/size mismatches, and oversized archive content are rejected.

File ordering, timestamps, permissions, metadata ordering, hashes, and certificate JSON remain deterministic for generated bundles. Verification does not extract archive paths to the filesystem.

The builder stays local-only. `publish()` fails closed, and this milestone does not authorize tags, GitHub Releases, registry publication, or asset upload.
