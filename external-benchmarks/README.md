# S3 External Benchmarks

`external-benchmarks/` is the repository-only laboratory for experiments that use S3 as a workload, validation environment, or correctness oracle to evaluate external systems.

The boundary is intentional:

- `benchmarks/` measures S3 itself;
- `external-benchmarks/` measures how external systems work with S3;
- external providers are never build, runtime, packaging, or main-CI dependencies of `s3-bootstrap`;
- external benchmark results are not automatically claims about S3 performance or language capability.

The first versioned campaign is **Agent Memory V1**. AI-MEMORY is an optional provider under test, not part of the compiler/runtime.

## Correctness-first

A scenario runs an external agent on an isolated S3 worktree, records safe provider/agent/execution metadata, and then executes deterministic S3 correctness oracles. Any failed oracle makes the scenario fail; invariant recall is informative only.

A campaign aggregates isolated scenario results from one provider repetition. A comparison aggregates complete repetitions from every provider and validates comparability before provider-to-provider claims are allowed.

## Discovery

```bash
python tools/external_bench.py --list
python tools/external_bench.py --list-campaigns
```

## Agent Memory V1

Provider arms:

- `no-memory`
- `context-only`
- `ai-memory`
- `ai-memory+s3-integrity-gate`

Read `campaigns/agent-memory-v1.md` for the scientific protocol and `campaigns/agent-memory-v1-execution.md` for the execution/result layout. Observation templates live under `templates/agent-memory-v1/`.

Every Agent Memory V1 scenario result carries a controlled execution profile (`s3_commit`, harness version, permissions profile, task protocol, repetition). The campaign aggregator rejects mixed profiles.

Aggregate one provider repetition:

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --result-dir results/agent-memory-v1/ai-memory/run-1 \
  --output-json results/agent-memory-v1/ai-memory/run-1/campaign.json
```

Compare all provider repetitions:

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --compare-root results/agent-memory-v1 \
  --output-json results/agent-memory-v1/comparison.json \
  --output-markdown results/agent-memory-v1/comparison.md
```

A comparison becomes `NOT_COMPARABLE` when a controlled variable differs. Metrics remain available for diagnosis, but capability claims are forbidden. The Markdown report is neutral and never selects a winner.

## Privacy and provider isolation

Network/provider runs are explicit/manual. Credentials, tokens, usernames, hostnames, personal paths, environment dumps, prompts/transcripts, and network identifiers must not be persisted in benchmark result documents. Provider SDKs must not be imported by the S3 compiler, runtime, `s3bench`, package entry point, or default CI.

## CI

External benchmark infrastructure is outside the default test path and main benchmark protocol. Validate it explicitly with:

```bash
python -m pytest -q external-benchmarks/tests
```

The dedicated `External Benchmarks` workflow remains manual-only and must not gate compiler correctness or releases.
