# External benchmark providers

Providers are systems under test or adapters used only by `external-benchmarks/`.
They are not S3 runtime providers and must never become dependencies of the
compiler, package, `s3bench`, or default CI.

The initial memory campaign reserves these provider identities:

- `no-memory`
- `context-only`
- `ai-memory`
- `ai-memory+s3-integrity-gate`

The v1 harness intentionally consumes a provider-neutral observation JSON rather
than importing vendor SDKs. This keeps the benchmark reproducible and lets a
campaign driver capture an AI-MEMORY, Codex, Claude Code, or other agent run
outside the S3 process before invoking the repository oracle.

A future adapter may automate setup/capture, but it must remain optional,
network-explicit, and isolated here. Never persist credentials, auth tokens,
full environment dumps, usernames, private hostnames, personal paths, or
network identifiers in result documents.
