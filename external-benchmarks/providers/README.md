# External benchmark providers

Providers are systems under test or adapters used only by `external-benchmarks/`.
They are not S3 runtime providers and must never become dependencies of the
compiler, package, `s3bench`, or default CI.

Agent Memory V1 reserves these provider identities:

- `no-memory`
- `context-only`
- `ai-memory`
- `ai-memory+s3-integrity-gate`

The harness consumes provider-neutral observation JSON rather than importing
vendor SDKs. Provider-specific setup, memory writes/reads, agent orchestration,
and network activity happen outside the S3 process. The resulting S3 observation
contains only safe benchmark metadata and is then evaluated by the repository
oracle.

The provider is the independent variable. Cross-provider comparison allows
provider ids/versions to differ, but requires controlled execution variables,
agent identities, and handoff identities to match across corresponding runs.

Do not persist credentials, auth tokens, full prompts/transcripts, full
environment dumps, usernames, private hostnames, personal paths, or network
identifiers in scenario, campaign, or comparison result documents.
