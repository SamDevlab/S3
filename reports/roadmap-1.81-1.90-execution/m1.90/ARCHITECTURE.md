# M1.90 Architecture

M1.90 builds deterministic local release-candidate bundles and an explicit target certification matrix. Structural and native execution evidence remain separate fields; Linux AArch64/macOS ARM64 native execution can remain deferred without being converted into structural or execution success.

A target is no longer marked `STRUCTURAL_PASS` merely because arbitrary bytes were supplied. Every target artifact requires a registered structural validator and must pass it before the certificate is emitted. Built-in Linux AArch64 validation checks ELF64/AArch64 identity; built-in macOS ARM64 validation checks Mach-O 64/ARM64 identity. Unknown targets require an explicit validator rather than receiving an automatic pass.

The RC bundle requires actual Apache-2.0 license text; there is no placeholder default LICENSE. Bundle metadata records `license=Apache-2.0`, and the existing deterministic toolchain bundle verifier is run before the candidate is returned. File ordering, timestamps, permissions, metadata ordering, hashes, and certificate JSON remain deterministic.

The builder stays local-only. `publish()` fails closed, and this milestone does not authorize tags, GitHub Releases, registry publication, or asset upload.
