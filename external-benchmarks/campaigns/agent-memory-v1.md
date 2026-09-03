# Agent Memory V1

`agent-memory-v1` is the first versioned S3 external benchmark campaign for durable AI-agent memory systems.

The campaign does **not** benchmark S3 runtime performance. It uses the S3 repository as a difficult, executable correctness oracle for external systems that claim to preserve engineering knowledge across time, sessions, or agents.

## Research question

Can a memory configuration help coding agents preserve current S3 architectural invariants during real repository work without increasing semantic regressions, accepting stale knowledge, or leaking state between benchmark cases?

The campaign compares these provider configurations:

1. `no-memory` — no durable state between phases;
2. `context-only` — only the active model context is available;
3. `ai-memory` — AI-MEMORY supplies durable external memory;
4. `ai-memory+s3-integrity-gate` — AI-MEMORY plus an S3-oriented validation layer.

AI-MEMORY remains an optional system under test. Nothing in the compiler, runtime, public package, `s3bench`, or main CI imports or requires it.

## Campaign cases

| Scenario | Mode | What it tests |
| --- | --- | --- |
| `memory.host-shell-policy.v1` | single-session | retention of shell-free host-process policy |
| `memory.ternary-subtraction.v1` | cross-session | balanced subtraction remains distinct from `NUMERIC_DIFFERENCE` / `TNDIFF` |
| `memory.checked-i64.v1` | cross-session | checked i64 overflow/division semantics survive later refactoring |
| `memory.mut-no-noalias.v1` | cross-session | `&mut` is not silently converted into a machine `noalias` promise |
| `memory.stale-memory.v1` | stale-memory | current repository evidence overrides an obsolete durable claim |
| `memory.cross-session.v1` | cross-session | multiple invariants survive a hard session boundary |
| `memory.cross-agent.v1` | cross-agent | multiple invariants survive handoff between distinct agent identities |

## Isolation protocol

Every scenario/repetition starts from a fresh clean worktree pinned to the same S3 commit used by the other provider configurations in the comparison.

Do not share:

- modified worktrees;
- hidden files;
- local notes;
- previous transcripts;
- unrecorded prompts;
- provider state from another scenario unless the scenario itself defines that state as its experimental input.

For `cross-session`, Session A is ended before Session B starts. Session B does not receive Session A's transcript. The configured durable memory mechanism is the only allowed persistent handoff channel.

For `cross-agent`, Agent B must be a distinct agent or harness identity and does not receive Agent A's transcript. Repository state and the configured durable memory system are the allowed handoff surfaces.

For `stale-memory`, inject the stale statement exactly as specified by the scenario. The desired behavior is not blind recall: the agent should compare it with the current checkout and prefer current authoritative evidence.

## Correctness-first rule

Reported recall is not a pass condition.

An agent may report every critical invariant and still fail the scenario if its resulting worktree violates an oracle. Conversely, a correct worktree can pass with incomplete explicit recall; that missing recall remains visible as an informative metric.

Campaign gate:

```text
any critical oracle failure -> scenario FAIL
any scenario FAIL          -> campaign FAIL
```

`mean_invariant_recall_rate` is descriptive and never overrides those gates.

## Running one scenario

After the external agent has completed its task in the isolated worktree, create an observation file:

```json
{
  "provider": {"id": "ai-memory", "version": "2.x"},
  "agent": {
    "provider": "openai",
    "model": "MODEL",
    "harness": "codex"
  },
  "reported_invariants": [
    "i64-overflow-no-wrap",
    "i64-division-failures"
  ]
}
```

Evaluate the worktree and persist the result using the scenario id as filename:

```bash
python tools/external_bench.py \
  --scenario memory.checked-i64.v1 \
  --observation-file observation.json \
  --repository-root /path/to/isolated/worktree \
  --output-json results/ai-memory/run-1/memory.checked-i64.v1.json
```

Repeat for every scenario. The recommended initial campaign is three repetitions per provider configuration.

## Aggregating one provider run

A result directory contains exactly one result for every campaign scenario:

```text
results/ai-memory/run-1/
  memory.host-shell-policy.v1.json
  memory.ternary-subtraction.v1.json
  memory.checked-i64.v1.json
  memory.mut-no-noalias.v1.json
  memory.stale-memory.v1.json
  memory.cross-session.v1.json
  memory.cross-agent.v1.json
```

Aggregate it with:

```bash
python tools/external_bench.py \
  --campaign agent-memory-v1 \
  --result-dir results/ai-memory/run-1 \
  --output-json results/ai-memory/run-1/campaign.json
```

The aggregator rejects mixed provider identities inside one run.

## Comparison discipline

A provider comparison is valid only when the following are held constant unless the scenario explicitly tests one of them:

- S3 commit;
- scenario version;
- agent model/version;
- agent harness/version;
- task text;
- tool permissions;
- operating-system/toolchain class needed by the oracle;
- number of repetitions.

Latency, token cost, retrieval volume, or provider-specific diagnostics may be collected separately, but Agent Memory V1 does not treat them as correctness gates.

## Minimum report

A published campaign report should include, per provider configuration:

- S3 commit under test;
- provider id/version;
- agent model/harness identity;
- number of repetitions;
- scenario pass/fail counts;
- critical oracle failure count;
- mean invariant recall rate;
- individual scenario result JSON files;
- any deviations from the protocol.

Do not publish credentials, tokens, personal paths, usernames, private hostnames, environment dumps, or network identifiers.
