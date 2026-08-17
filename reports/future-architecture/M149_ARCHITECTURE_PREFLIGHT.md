# M1.49 Architecture Preflight

Status: `ARCHITECTURE_UNRESOLVED` and `BLOCKED_BY_ENVIRONMENT`.

The repository has enough evidence to require a versioned WASI target and a
runtime matrix, but not enough implementation evidence to accept a specific
core-module versus component boundary. Current official WASI material now
describes Preview 2 as stable and the Component Model/WASI line is evolving;
selecting one here would create a new ABI contract without an S3 backend.

The unresolved decisions are target name, module/component format, runtime
authority, import namespace, linear-memory ABI, capability mapping, and
deterministic artifact encoding. No WASI behavior is invented by this report.

Official reference: https://github.com/WebAssembly/WASI.
