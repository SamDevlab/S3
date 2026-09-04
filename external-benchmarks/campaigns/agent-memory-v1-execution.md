# Agent Memory V1 execution kit

This kit turns `agent-memory-v1` into a repeatable four-arm experiment without coupling S3 to any model or memory SDK.

## Directory contract

```text
results/agent-memory-v1/
  no-memory/run-1/ ... run-3/
  context-only/run-1/ ... run-3/
  ai-memory/run-1/ ... run-3/
  ai-memory+s3-integrity-gate/run-1/ ... run-3/
```

Every scenario is executed in a fresh worktree. `run-N` is a logical repetition identifier; scenarios do not share one modified worktree.

## Required execution metadata

Every Agent Memory V1 observation must include:

```json
{
  "execution": {
    "s3_commit": "<pinned-s3-commit>",
    "agent_harness_version": "<version>",
    "tool_permissions_profile": "<stable-profile-id>",
    "task_protocol_version": "agent-memory-v1",
    "repetition": 1
  }
}
```

The provider is the independent variable. The campaign aggregator requires one execution profile inside a provider repetition. Cross-provider comparison requires the same S3 commit, harness version, permissions profile, task protocol, scenario version, agent identity, and handoff identity across every corresponding provider and repetition. Controlled-variable drift between repetitions is also rejected.

## Provider arms

- `no-memory`: no durable memory service.
- `context-only`: active context is allowed, but no external durable memory survives a hard boundary.
- `ai-memory`: AI-MEMORY is the durable memory channel.
- `ai-memory+s3-integrity-gate`: the same memory provider plus the experimental S3 integrity validation layer.

## Prepare one provider repetition

Generate the deterministic plan before running agents:

```bash
python tools/external_bench.py \
  --prepare-run \
  --campaign agent-memory-v1 \
  --provider ai-memory \
  --provider-version 2.x \
  --repetition 1 \
  --s3-commit COMMIT \
  --agent-provider openai \
  --agent-model MODEL \
  --agent-harness codex \
  --agent-harness-version VERSION \
  --tool-permissions-profile standard \
  --output-json results/agent-memory-v1/ai-memory/run-1/plan.json
```

`--prepare-run` is offline. It does not create worktrees or invoke agents/providers. It emits the canonical run root and seven scenario records containing:

- the scenario/mode;
- the observation template;
- a unique worktree key;
- observation/result paths;
- required handoff or stale-memory evidence;
- the normative stale claim id where applicable.

Use the plan as the handoff contract for whichever external orchestration actually creates the clean worktrees and runs the agent.

## Handoff evidence

Cross-session and cross-agent observations record `source_agent`, `target_agent`, and `transcript_reused: false`. Cross-agent source and target identities must differ.

## Stale-memory evidence

The stale-memory case must record:

```json
{"stale_memory": {"claim_id": "ffi-is-future-work", "injected": true}}
```

The aggregator rejects another claim id.

## One scenario

```bash
python tools/external_bench.py \
  --scenario memory.checked-i64.v1 \
  --observation-file observation.json \
  --repository-root /path/to/fresh/worktree \
  --output-json results/agent-memory-v1/ai-memory/run-1/memory.checked-i64.v1.json
```

## One provider repetition

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --result-dir results/agent-memory-v1/ai-memory/run-1 \
  --output-json results/agent-memory-v1/ai-memory/run-1/campaign.json
```

## Four-provider comparison

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --compare-root results/agent-memory-v1 \
  --output-json results/agent-memory-v1/comparison.json \
  --output-markdown results/agent-memory-v1/comparison.md
```

The comparison is `NOT_COMPARABLE` when a controlled variable differs. Metrics remain available for diagnosis, but provider-to-provider capability claims are forbidden. The report is neutral and never selects a winner.

For an exploratory smoke run, `--repetitions 1` may override the recommended three repetitions; published results should label such a run exploratory.
