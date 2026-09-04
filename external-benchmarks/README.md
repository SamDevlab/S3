# S3 External Benchmarks

`external-benchmarks/` is the repository-only laboratory for experiments that use S3 as a workload, validation environment, or correctness oracle to evaluate external systems.

The boundary is intentional:

- `benchmarks/` measures S3 itself;
- `external-benchmarks/` measures how external systems work with S3;
- external providers are never build, runtime, packaging, or main-CI dependencies of `s3-bootstrap`;
- external benchmark results are not automatically claims about S3 performance or language capability.

The first versioned campaign is **Agent Memory V1**. AI-MEMORY is an optional provider under test, not part of the compiler/runtime. No operation in this laboratory creates branches, issues, pull requests, comments, or commits in the upstream AI-MEMORY repository.

## Correctness-first

A scenario runs an external agent on an isolated S3 subject worktree, records safe provider/agent/execution metadata, and then executes deterministic S3 correctness oracles. Any failed oracle makes the scenario fail; invariant recall is informative only.

Agent Memory V1 also has a task-artifact gate: a coding scenario must produce the scoped repository change declared by the task pack. A no-op cannot pass simply because the pre-existing tests are green.

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

The campaign pins the S3 subject commit in `campaigns/agent-memory-v1.json`. The benchmark controller may continue to evolve on `external-benchmarks-v1`, while every compared agent works on the same detached subject commit. This also prevents the subject agent from seeing the controller-only `external-benchmarks/` oracle/task infrastructure when that directory is absent from the pinned subject revision.

Read `campaigns/agent-memory-v1.md` for the scientific protocol and `campaigns/agent-memory-v1-execution.md` for the execution/result layout. The task pack lives at `task-packs/agent-memory-v1.json`.

Prepare a deterministic run plan before executing any external agent:

```bash
python tools/external_bench.py \
  --prepare-run \
  --campaign agent-memory-v1 \
  --provider ai-memory \
  --provider-version 2.x \
  --repetition 1 \
  --s3-commit db5f4bf10e2066f52bf144d23e6f7db56154e298 \
  --agent-provider openai \
  --agent-model MODEL \
  --agent-harness codex \
  --agent-harness-version VERSION \
  --tool-permissions-profile standard \
  --output-json results/agent-memory-v1/ai-memory/run-1/plan.json
```

The plan does not invoke a model, memory provider, network call, or Git worktree operation.

## Offline protocol smoke

Validate the full V1 experiment structure without making any memory-provider claim:

```bash
python tools/external_bench_smoke.py \
  --workspace-root /tmp/s3-agent-memory-v1-smoke \
  --with-oracles \
  --output-json /tmp/s3-agent-memory-v1-smoke.json
```

The smoke must cover exactly:

- 4 provider arms;
- 7 scenarios;
- 28 provider/scenario bundles;
- 52 phase steps;
- 28 synthetic observations;
- 7 semantic S3 oracles against the pinned subject commit.

Smoke results always contain `"scientific_claims_allowed": false`. They prove protocol wiring/oracle health only. Real provider comparisons require actual agent executions.

## Privacy and provider isolation

Network/provider runs are explicit/manual. Credentials, tokens, usernames, hostnames, personal paths, environment dumps, prompts/transcripts, and network identifiers must not be persisted in benchmark result documents. The recall sidecar is deliberately minimal and stores only the schema version plus recalled invariant IDs.

Provider SDKs must not be imported by the S3 compiler, runtime, `s3bench`, package entry point, or default compiler CI.

## CI

External benchmark infrastructure is outside the default pytest path and main benchmark protocol. Validate it explicitly with:

```bash
python -m pytest -q external-benchmarks/tests
```

The dedicated `External Benchmarks` workflow runs for relevant pull-request changes and may also be started manually. It is an infrastructure validation workflow; it performs no live model/provider call and is not a release/performance gate for S3 itself.
