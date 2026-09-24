# External benchmark providers

Providers are systems under test or optional repository-only adapters used by
`external-benchmarks/`. They are not S3 runtime providers and must never become
dependencies of the compiler, package, `s3bench`, or default CI.

Agent Memory V1 reserves these provider identities:

- `no-memory`
- `context-only`
- `ai-memory`
- `ai-memory+s3-integrity-gate`

The generic harness consumes provider-neutral observation JSON. Provider-specific
adapters may live below this directory when they improve reproducibility, but
they must remain optional, stdlib-only where practical, explicit about network
or process execution, and isolated from the S3 compiler/runtime.

The initial `providers/ai_memory/` adapter follows that rule:

- read-only diagnostics use AI-MEMORY's public `/api/v1` surface;
- managed agent launches use the host `ai-memory run` executable;
- credentials stay in environment/runtime memory and are never persisted;
- native stdout/stderr transcripts are not captured into benchmark artifacts;
- no upstream repository mutation is performed or required.

The provider is the independent variable. Cross-provider comparison allows
provider ids/versions to differ, but requires controlled execution variables,
agent identities, and handoff identities to match across corresponding runs.

Do not persist credentials, auth tokens, full prompts/transcripts, full
environment dumps, usernames, private hostnames, personal paths, or network
identifiers in scenario, campaign, provider-probe, or comparison result
documents.
