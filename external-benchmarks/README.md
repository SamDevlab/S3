# S3 External Benchmarks

`external-benchmarks/` is the repository-only laboratory for experiments that use S3 as a workload, validation environment, or correctness oracle to evaluate external systems.

The boundary is intentional:

- `benchmarks/` measures S3 implementations, runtime behavior, compilation, native execution, and comparable performance evidence;
- `external-benchmarks/` measures how external systems work with S3;
- external providers are never build, runtime, packaging, or main-CI dependencies of `s3-bootstrap`;
- external benchmark results are not automatically claims about S3 performance or language capability.

The first supported experiment class is agent memory. AI-MEMORY is treated as an optional provider under test, not as part of the compiler or runtime.

## Correctness-first model

External benchmarks evaluate consequences in a prepared worktree. Repeating an invariant is informative; preserving the invariant in the resulting repository is what decides correctness.

A run has three parts:

1. an external system/agent operates on an S3 worktree;
2. an observation records provider/model metadata and any invariants the agent surfaced;
3. the oracle executes deterministic checks against the resulting worktree.

Oracle checks currently support:

- argument-vector commands executed with `shell=False`;
- required literal patterns over explicit repository globs;
- forbidden literal patterns over explicit repository globs.

Any failed oracle check makes the scenario fail. Invariant recall is reported separately and never overrides a correctness failure.

## Layout

```text
external-benchmarks/
  README.md
  harness/
    __init__.py
    core.py
    cli.py
  providers/
    README.md
  scenarios/
    memory.host-shell-policy.v1.json
  schema/
    scenario-1.0.0.schema.json
    result-1.0.0.schema.json
  tests/
    test_harness.py
tools/
  external_bench.py
```

## Run

List scenarios:

```bash
python tools/external_bench.py --list
```

Prepare an observation file after the external agent has worked on the checkout:

```json
{
  "provider": {"id": "ai-memory", "version": "2.x"},
  "agent": {"provider": "openai", "model": "MODEL", "harness": "codex"},
  "reported_invariants": ["host-process-no-shell"]
}
```

Evaluate the worktree:

```bash
python tools/external_bench.py \
  --scenario memory.host-shell-policy.v1 \
  --observation-file observation.json \
  --output-json external-result.json
```

The command exits non-zero when a correctness oracle fails.

## Providers

Provider integrations belong under `providers/` and must remain optional. A provider adapter must not be imported by the S3 compiler, runtime, package entry point, `s3bench`, or default test suite.

Network-backed runs should be explicit/manual. Credentials, tokens, usernames, hostnames, personal paths, environment dumps, and network identifiers must not be persisted in benchmark results.

## CI policy

The external benchmark harness is intentionally outside the default `pytest` test path and outside the main S3 benchmark protocol. Its own deterministic harness tests can be run with:

```bash
python -m pytest -q external-benchmarks/tests
```

Network/provider campaigns should use an explicit manual workflow when one is added. They must not gate compiler correctness or releases.

## First research direction

The initial memory campaign should compare configurations such as `no-memory`, `context-only`, `ai-memory`, and eventually `ai-memory+s3-integrity-gate` across scenarios for invariant retention, stale-memory rejection, cross-session handoff, cross-agent handoff, contradiction resistance, and semantic regression prevention.
