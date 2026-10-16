# S3 ecosystem (parallel foundation)

This tree adds user-facing tools, experimental libraries, reproducible
applications, and a local VS Code extension without changing the compiler or
the `stdlib/s3/v1` contracts. The compiler baseline is pinned to
`2eab8a43f07b7fc842c4036ea0fb0203a9d41d6c`; application manifests and lab
reports carry that identity.

Start with [getting started](getting-started.md), then use the
[capability matrix](capability-matrix.md) and
[experimental library contracts](library-contracts.md) to understand what is
implemented versus intentionally unsupported. The
[learning path](learning-path.md) is backed by executable S3 tests and leads
into the five application projects. Editor setup and its precise LSP limits
are in `ecosystem/editors/vscode-s3/README.md`.

The lab distinguishes compilation, hosted execution, native execution, and FFI.
Only compile-only and hosted modes are qualified on the current Windows host.
Unsupported modes remain explicit failures/unsupported results; they are never
counted as passes. No package or extension is published by this repository.
