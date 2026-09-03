# S3 External Benchmarks

`external-benchmarks/` is the repository-only laboratory for experiments that use S3 as a workload, validation environment, or correctness oracle to evaluate external systems.

The boundary is intentional:

- `benchmarks/` measures S3 implementations, runtime behavior, compilation, native execution, and comparable performance evidence;
- `external-benchmarks/` measures how external systems work with S3;
- external providers are never build, runtime, packaging, or main-CI dependencies of `s3-bootstrap`;
- external benchmark results are not automatically claims about S3 performance or language capability.

The first versioned campaign is **Agent Memory V1**. AI-MEMORY is treated as an optional provider under test, not as part of the compiler or runtime.

## Correctness-first model

External benchmarks evaluate consequences in a prepared worktree. Repeating an invariant is informative; preserving the invariant in the resulting repository is what decides correctness.

A scenario run has three parts:

1. an external system/agent operates on an isolated S3 worktree;
2. an observation records provider/model metadata and any invariants the agent surfaced;
3. the oracle executes deterministic checks against the resulting worktree.

Oracle checks currently support:

- argument-vector commands executed with `shell=False`;
- required literal patterns over explicit repository globs;
- forbidden literal patterns over explicit repository globs.

Any failed oracle check makes the scenario fail. Invariant recall is reported separately and never overrides a correctness failure.

A campaign aggregates persisted scenario results. It does not execute multiple scenarios against the same worktree: isolation is part of the benchmark contract.

## Layout

```text
external-benchmarks/
  README.md
  campaigns/
    agent-memory-v1.json
    agent-memory-v1.md
  harness/
    __init__.py
    campaign.py
    core.py
    cli.py
  providers/
    README.md
  scenarios/
    memory.host-shell-policy.v1.json
    memory.ternary-subtraction.v1.json
    memory.checked-i64.v1.json
    memory.mut-no-noalias.v1.json
    memory.stale-memory.v1.json
    memory.cross-session.v1.json
    memory.cross-agent.v1.json
  schema/
    scenario-1.0.0.schema.json
    result-1.0.0.schema.json
    campaign-1.0.0.schema.json
    campaign-result-1.0.0.schema.json
  tests/
    test_harness.py
    test_campaign.py
tools/
  external_bench.py
```

## Discovery

List scenarios:

```bash
python tools/external_bench.py --list
```

List campaigns:

```bash
python tools/external_bench.py --list-campaigns
```

## Run one scenario

Prepare an observation file after the external agent has worked on an isolated checkout:

```json
{
  "provider": {"id": "ai-memory", "version": "2.x"},
  "agent": {"provider": "openai", "model": "MODEL", "harness": "codex"},
  "reported_invariants": ["host-process-no-shell"]
}
```

Evaluate that worktree:

```bash
python tools/external_bench.py \
  --scenario memory.host-shell-policy.v1 \
  --observation-file observation.json \
  --repository-root /path/to/isolated/worktree \
  --output-json memory.host-shell-policy.v1.json
```

The command exits non-zero when a correctness oracle fails.

## Agent Memory V1

The first campaign compares:

- `no-memory`;
- `context-only`;
- `ai-memory`;
- `ai-memory+s3-integrity-gate`.

It covers ordinary invariant retention, balanced-vs-machine subtraction semantics, checked i64, mutable-reference alias assumptions, stale-memory rejection, cross-session handoff, and cross-agent handoff.

Read the complete protocol in [`campaigns/agent-memory-v1.md`](campaigns/agent-memory-v1.md).

Each scenario/repetition must use a fresh clean worktree. Persist one result JSON per scenario, all from the same provider configuration, then aggregate:

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --result-dir results/ai-memory/run-1 \
  --output-json results/ai-memory/run-1/campaign.json
```

The campaign fails when any scenario oracle fails. Mean invariant recall remains informative only.

## Providers

Provider integrations belong under `providers/` and must remain optional. A provider adapter must not be imported by the S3 compiler, runtime, package entry point, `s3bench`, or default test suite.

Network-backed runs are explicit/manual. Credentials, tokens, usernames, hostnames, personal paths, environment dumps, and network identifiers must not be persisted in benchmark results.

## CI policy

The external benchmark harness is intentionally outside the default `pytest` test path and outside the main S3 benchmark protocol. Its deterministic harness/campaign tests can be run with:

```bash
python -m pytest -q external-benchmarks/tests
```

The dedicated `External Benchmarks` workflow is manual-only. Network/provider campaigns must not gate compiler correctness or releases.
