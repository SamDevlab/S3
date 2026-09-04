# Agent Memory V1

`agent-memory-v1` is the first versioned S3 external benchmark campaign for durable AI-agent memory systems. It does not benchmark S3 runtime performance; it uses the S3 repository as an executable correctness oracle.

## Research question

Can a memory configuration help coding agents preserve current S3 architectural invariants during real repository work without increasing semantic regressions, accepting stale knowledge, or leaking state between benchmark cases?

## Provider configurations

1. `no-memory` — no durable state between phases;
2. `context-only` — active model context only;
3. `ai-memory` — AI-MEMORY supplies durable external memory;
4. `ai-memory+s3-integrity-gate` — AI-MEMORY plus S3-oriented validation before durable conclusions are trusted.

AI-MEMORY remains optional. Nothing in the compiler, runtime, public package, `s3bench`, or main CI imports or requires it.

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

Every scenario/repetition starts from a fresh clean worktree pinned to the same S3 commit used by the other provider configurations. Do not share modified worktrees, hidden files, local notes, previous transcripts, unrecorded prompts, or provider state from another scenario unless the scenario defines that state as experimental input.

For cross-session, Session A ends before Session B starts and Session B does not receive the prior transcript. For cross-agent, Agent B is a distinct identity and receives no Agent A transcript. For stale-memory, inject the declared stale statement unchanged and require reconciliation against current repository evidence.

## Controlled execution evidence

Every Agent Memory V1 observation records:

```json
{
  "execution": {
    "s3_commit": "PINNED_COMMIT",
    "agent_harness_version": "HARNESS_VERSION",
    "tool_permissions_profile": "PROFILE",
    "task_protocol_version": "agent-memory-v1",
    "repetition": 1
  }
}
```

A provider repetition is rejected when its scenario results do not share exactly one execution profile/repetition.

Cross-session/cross-agent cases also record `source_agent`, `target_agent`, and `transcript_reused: false`. Cross-agent source/target identities must differ.

The stale-memory case uses the normative claim id:

```json
{"stale_memory": {"claim_id": "ffi-is-future-work", "injected": true}}
```

Any other claim id is rejected by the campaign aggregator.

## Correctness-first rule

```text
any critical oracle failure -> scenario FAIL
any scenario FAIL          -> provider repetition FAIL
```

Recall is descriptive and never overrides these gates.

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

The comparison checks the S3 commit, harness version, permissions profile, task-protocol version, scenario versions, agent identities, and handoff identities across providers. A mismatch yields `NOT_COMPARABLE`; no provider-to-provider capability claim should then be made.

The report deliberately does not rank or select a winner. It reports campaign-run PASS counts, scenario pass rates, critical oracle failures, and mean invariant recall separately.

The recommended campaign uses three repetitions per provider. `--repetitions 1` is allowed for exploratory smoke runs only.

See `agent-memory-v1-execution.md` for directory layout and observation templates.

## Minimum published report

Include the pinned S3 commit, provider id/version, agent model/harness identity, repetitions, scenario pass/fail counts, critical oracle failures, mean invariant recall, individual result JSON files, protocol evidence, comparability status/reasons, and deviations from protocol.

Never publish credentials, tokens, personal paths, usernames, private hostnames, prompts/transcripts, environment dumps, or network identifiers.
