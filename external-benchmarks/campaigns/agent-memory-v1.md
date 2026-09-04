# Agent Memory V1

`agent-memory-v1` is the first versioned S3 external benchmark campaign for durable AI-agent memory systems. It does not benchmark S3 runtime performance; it uses a pinned S3 repository revision as an executable correctness oracle.

## Research question

Can a memory configuration help coding agents preserve current S3 architectural invariants during real repository work without increasing semantic regressions, accepting stale knowledge, or leaking state between benchmark cases?

## Provider configurations

1. `no-memory` — no durable state between phases;
2. `context-only` — active model context only;
3. `ai-memory` — AI-MEMORY supplies durable external memory;
4. `ai-memory+s3-integrity-gate` — AI-MEMORY plus S3-oriented validation before durable conclusions are trusted.

AI-MEMORY remains optional. Nothing in the compiler, runtime, public package, `s3bench`, or normal S3 build imports or requires it. This campaign never writes to the upstream AI-MEMORY repository.

## Controller and subject

The benchmark controller lives on the external-benchmark development branch. The **subject S3 commit** is independently pinned in the campaign manifest:

```text
db5f4bf10e2066f52bf144d23e6f7db56154e298
```

Every provider/repetition/scenario uses a detached worktree of that same subject commit. `--prepare-run` rejects a different subject SHA.

This split is intentional: the controller can contain task packs, provider adapters, and oracles while the coding agent works on the frozen S3 subject revision. The subject therefore does not gain access to controller-only benchmark internals merely because the harness evolves.

## Campaign cases

| Scenario | Mode | What it tests |
| --- | --- | --- |
| `memory.host-shell-policy.v1` | single-session | shell-free host-process policy |
| `memory.ternary-subtraction.v1` | cross-session | balanced subtraction remains distinct from `NUMERIC_DIFFERENCE` / `TNDIFF` |
| `memory.checked-i64.v1` | cross-session | checked i64 semantics survive later refactoring |
| `memory.mut-no-noalias.v1` | cross-session | `&mut` is not silently converted into machine `noalias` |
| `memory.stale-memory.v1` | stale-memory | current repository evidence overrides obsolete durable knowledge |
| `memory.cross-session.v1` | cross-session | multiple invariants survive a hard session boundary |
| `memory.cross-agent.v1` | cross-agent | invariants survive handoff between distinct agent identities |

## Isolation protocol

Every scenario/repetition starts from a fresh clean worktree pinned to the subject commit. Do not share modified worktrees, hidden files, local notes, previous transcripts, unrecorded prompts, or provider state from another scenario unless the scenario defines that state as experimental input.

For cross-session, Session A ends before Session B starts and Session B does not receive the prior transcript. For cross-agent, Agent B is a distinct recorded identity and receives no Agent A transcript. For stale-memory, inject the declared stale statement unchanged and require reconciliation against current repository evidence.

The worktree orchestrator records only worktrees it created and refuses to remove a dirty experiment unless the operator explicitly chooses to discard those changes.

## Versioned task pack

`external-benchmarks/task-packs/agent-memory-v1.json` defines the actual coding work for all seven scenarios. Each entry contains Phase A/Phase B instructions, authoritative paths, required changed-file scopes, forbidden changed-file scopes, and a maximum changed-file budget.

The stale-memory Phase A intentionally does **not** expose the current FFI invariant. It supplies the obsolete claim under test and requires the later phase to resolve it against the subject checkout.

## Correctness-first and task-completion gates

A scenario passes only when both classes of checks pass:

```text
semantic S3 oracle PASS
        +
required task artifact/diff PASS
        =
scenario PASS
```

Therefore:

```text
any critical oracle failure -> scenario FAIL
no required coding change    -> scenario FAIL
forbidden/out-of-scope change-> scenario FAIL
any scenario FAIL            -> provider repetition FAIL
```

Recall is descriptive and never overrides these gates.

## Recall evidence

At the end of the coding phase, the agent may write exactly one minimal sidecar:

```json
{"schema_version":"1.0.0","reported_invariants":["invariant-id"]}
```

The sidecar is excluded from the coding-diff gate and must never contain transcript, prompt text, repository excerpts, credentials, paths, or free-form notes. It is evidence only and cannot be used as a handoff channel.

## Controlled execution evidence

Every Agent Memory V1 observation records:

```json
{
  "execution": {
    "s3_commit": "db5f4bf10e2066f52bf144d23e6f7db56154e298",
    "agent_harness_version": "HARNESS_VERSION",
    "tool_permissions_profile": "PROFILE",
    "task_protocol_version": "agent-memory-v1",
    "repetition": 1
  }
}
```

A provider repetition is rejected when its scenario results do not share exactly one execution profile/repetition.

Cross-session/cross-agent cases also record `source_agent`, `target_agent`, and `transcript_reused: false`. Cross-agent source/target identities must differ, and direct provider runbooks require a distinct receiving command as well as a distinct identity.

The stale-memory case uses the normative claim id:

```json
{"stale_memory": {"claim_id": "ffi-is-future-work", "injected": true}}
```

Any other claim id is rejected by the campaign aggregator.

## Offline protocol smoke

Before live provider calls, the controller validates the whole experiment graph offline:

```text
4 providers × 7 scenarios = 28 bundles
52 phase steps
28 synthetic observations
7 semantic subject oracles
```

The smoke is not evidence that one memory provider is better than another. Its result always contains `scientific_claims_allowed: false`.

## Aggregation and comparison

Run all seven scenarios in isolated worktrees, persist one scenario result per file, then aggregate one provider repetition:

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --result-dir results/agent-memory-v1/ai-memory/run-1 \
  --output-json results/agent-memory-v1/ai-memory/run-1/campaign.json
```

After all provider repetitions exist, compare them:

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --compare-root results/agent-memory-v1 \
  --output-json results/agent-memory-v1/comparison.json \
  --output-markdown results/agent-memory-v1/comparison.md
```

The comparison checks the S3 commit, harness version, permissions profile, task-protocol version, scenario versions, agent identities, handoff identities, and provider-profile consistency. A mismatch yields `NOT_COMPARABLE`; no provider-to-provider capability claim should then be made.

The report deliberately does not rank or select a winner. It reports campaign-run PASS counts, scenario pass rates, critical oracle failures, and mean invariant recall separately.

The recommended campaign uses three repetitions per provider. A one-repetition real run is exploratory only.

See `agent-memory-v1-execution.md` for the operational sequence.

## Minimum published report

Include the pinned S3 subject commit, provider id/version and provider profile, agent model/harness identity, repetitions, scenario pass/fail counts, critical oracle failures, mean invariant recall, individual result JSON files, protocol evidence, comparability status/reasons, and deviations from protocol.

Never publish credentials, tokens, personal paths, usernames, private hostnames, prompts/transcripts, environment dumps, or network identifiers.
