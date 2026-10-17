# Agent Memory V1 execution kit

This kit turns `agent-memory-v1` into a repeatable four-arm experiment without coupling S3 to any model or memory SDK.

The execution contract is `agent-memory-v1.0.3`. It keeps the task pack and
semantic oracles unchanged, but persists structured return-code evidence for
each required agent phase.

## Subject/controller split

The controller is the `external-benchmarks-v1` branch. The S3 subject under test is pinned by the campaign manifest and must be identical across every provider/repetition:

```text
db5f4bf10e2066f52bf144d23e6f7db56154e298
```

The run-plan builder rejects another `s3_commit`. Each scenario runs in its own detached worktree of that subject commit. The worktree root must be outside the controller repository.

## Directory contract

```text
results/agent-memory-v1/
  no-memory/run-1/ ... run-3/
  context-only/run-1/ ... run-3/
  ai-memory/run-1/ ... run-3/
  ai-memory+s3-integrity-gate/run-1/ ... run-3/
```

Within a run directory, the controller may create `plan.json`, `runbook.json`, rendered prompts, observations, scenario results, and `campaign.json`. Absolute worktree paths are operational state only and are not part of scientific result documents.

## 1. Prepare a provider repetition

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
  --tool-permissions-profile windows-danger-full-access-v1 \
  --output-json results/agent-memory-v1/ai-memory/run-1/plan.json
```

The provider is the independent variable. Model, harness version, permissions profile, task protocol, subject commit, scenario versions, and corresponding handoff identities are controlled variables.

## 2. Prepare isolated subject worktrees

Preview first:

```bash
python tools/external_bench_worktrees.py prepare \
  --plan-file results/agent-memory-v1/ai-memory/run-1/plan.json \
  --worktree-root /tmp/s3-agent-memory-v1-worktrees \
  --preview
```

Create them:

```bash
python tools/external_bench_worktrees.py prepare \
  --plan-file results/agent-memory-v1/ai-memory/run-1/plan.json \
  --worktree-root /tmp/s3-agent-memory-v1-worktrees \
  --execute
```

Cleanup refuses to delete dirty experiment worktrees unless the operator explicitly supplies the discard option. This prevents silent loss of an unfinished run.

## 3. Render task prompts and runbook

The versioned task pack is `external-benchmarks/task-packs/agent-memory-v1.json` (version `1.0.1`, superseding `1.0.0` for future real runs). It defines Phase A/Phase B instructions, authoritative paths, required changed-file scopes, explicit alternatives for equivalent focused test files, forbidden changed-file scopes, and a change budget.

For the next comparable Windows execution, use `windows-danger-full-access-v1` as the same effective `tool_permissions_profile` in all four provider arms. The previous `workspace-write` divergence is historical and does not make the prior real runs reusable.

For direct arms, provide the same native agent command used for that experimental arm. Cross-agent cases require an explicit, different receiving-agent identity and command. AI-MEMORY arms use the managed AI-MEMORY launcher and fresh native sessions.

Every managed invocation must explicitly receive its phase-specific prompt:

```text
--prompt-file <run-directory>/prompts/<scenario>.<phase>.md
```

The adapter validates that this is a non-empty UTF-8 file inside the run-plan
directory and sends only that invocation's contents through stdin. It records
only `prompt_delivery=stdin` and `prompt_present=true`; prompt content and
process output are not persisted as scientific evidence.

Example:

```bash
python tools/external_bench_runbook.py \
  --plan-file results/agent-memory-v1/ai-memory/run-1/plan.json \
  --run-dir results/agent-memory-v1/ai-memory/run-1 \
  --target-agent-file target-agent.json
```

Prompts instruct the agent to write only the minimal recall sidecar at the end of the coding phase:

```json
{"schema_version":"1.0.0","reported_invariants":["invariant-id"]}
```

The sidecar is evidence only. It is forbidden as a handoff/memory channel and is excluded from the task-diff gate.

## 4. Run the agent phases

`no-memory` and `context-only` use provider-neutral direct argv execution. AI-MEMORY arms use the optional `ai-memory run` adapter already implemented under `external-benchmarks/providers/ai_memory/`.

Hard-boundary rules:

- cross-session: end Phase A and start Phase B with no native transcript reuse;
- cross-agent: Phase B must use a distinct recorded agent/harness identity;
- AI-MEMORY is the only durable handoff channel in AI-MEMORY arms;
- no hidden note files or unrecorded handoff channels are permitted.

The `stale-memory` task deliberately injects `ffi-is-future-work`. Its Phase A does not reveal the current FFI invariant; the receiving phase must reconcile the stale claim against the current subject checkout.

## 5. Materialize observation evidence

Prefer deriving handoff identity from the actual runbook and recall from the agent sidecar:

```bash
python tools/external_bench_observation.py \
  --plan-file results/agent-memory-v1/ai-memory/run-1/plan.json \
  --runbook-file results/agent-memory-v1/ai-memory/run-1/runbook.json \
  --scenario memory.cross-session.v1 \
  --agent-report-file /tmp/s3-agent-memory-v1-worktrees/ai-memory/run-1/memory.cross-session.v1/.s3-agent-memory-report.json \
  --output-json results/agent-memory-v1/ai-memory/run-1/memory.cross-session.v1.observation.json
```

No prompt, transcript, credential, hostname, environment dump, or personal path is copied into the observation.

## 6. Evaluate one scenario

```bash
python tools/external_bench.py \
  --scenario memory.checked-i64.v1 \
  --observation-file results/agent-memory-v1/ai-memory/run-1/memory.checked-i64.v1.observation.json \
  --repository-root /tmp/s3-agent-memory-v1-worktrees/ai-memory/run-1/memory.checked-i64.v1 \
  --output-json results/agent-memory-v1/ai-memory/run-1/memory.checked-i64.v1.json
```

For Agent Memory V1, a new-protocol scenario is `VALID_PASS` only when all
three independent dimensions pass:

1. required agent processes finish with return code `0`;
2. semantic S3 oracle checks;
3. task-artifact checks proving the required scoped change was actually made.

A completed required agent process with a nonzero return code is a valid
`VALID_FAIL`, even when the other two dimensions pass. A watchdog timeout is
`INVALID_OPERATIONAL_RUN`; missing required process metadata is
`INVALID_EXECUTION_EVIDENCE`. Auxiliary commands do not affect the agent
process dimension. Semantic and task-artifact checks remain diagnostic and are
still evaluated whenever enough evidence is available.

Process metadata contains only phase, agent identity, runner, sanitized argv,
return code, timeout state, and elapsed time. It never stores transcripts,
prompts, credentials, environment dumps, or memory contents.

A no-op therefore fails even when the baseline tests already pass.

## 7. Aggregate one repetition

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --result-dir results/agent-memory-v1/ai-memory/run-1 \
  --output-json results/agent-memory-v1/ai-memory/run-1/campaign.json
```

## 8. Compare providers

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --compare-root results/agent-memory-v1 \
  --output-json results/agent-memory-v1/comparison.json \
  --output-markdown results/agent-memory-v1/comparison.md
```

The comparison becomes `NOT_COMPARABLE` on controlled-variable drift, including collective drift between repetitions. The report never selects a winner automatically.

## Offline smoke before live execution

Before spending model/provider calls, validate all protocol wiring:

```bash
python tools/external_bench_smoke.py \
  --workspace-root /tmp/s3-agent-memory-v1-smoke \
  --with-oracles \
  --output-json /tmp/s3-agent-memory-v1-smoke.json
```

The smoke covers exactly 4 providers × 7 scenarios = 28 bundles and 52 phase steps, and validates all seven semantic oracles against the pinned subject commit. Synthetic observations deliberately report every invariant so the smoke tests plumbing, not memory quality.

Every smoke artifact says:

```json
{"scientific_claims_allowed": false}
```

Only real agent executions may be used for provider capability claims.

## Real campaign size

Exploratory run:

```text
4 providers × 7 scenarios × 1 repetition = 28 live agent scenario executions
```

Recommended V1 campaign:

```text
4 providers × 7 scenarios × 3 repetitions = 84 live agent scenario executions
```

Live provider/model calls remain explicit and operator-controlled. The S3 repository never writes to the upstream AI-MEMORY repository.
