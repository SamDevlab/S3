# AI-MEMORY provider adapter

This directory contains the optional host-side adapter used to exercise the
`ai-memory` and `ai-memory+s3-integrity-gate` arms of Agent Memory V1.

It is intentionally **not** part of the S3 compiler/runtime/package. The adapter
uses only Python's standard library plus an `ai-memory` executable already
installed by the benchmark operator.

## Boundaries

- HTTP access is restricted to documented read-only `/api/v1/*` routes.
- The adapter never reads or writes AI-MEMORY's wiki or SQLite files directly.
- `AI_MEMORY_AUTH_TOKEN` is read from the environment only and is never emitted
  into probe, scenario, campaign, or comparison JSON.
- Probe output does not persist the server URL/hostname.
- Agent processes are launched through documented `ai-memory run` argv with
  `shell=False`.
- stdout/stderr are not captured by the adapter, so native prompts/transcripts do
  not become benchmark artifacts.
- Actual process execution requires the explicit `run ... --execute` command.
- No operation in this adapter creates issues, branches, commits, comments, or
  pull requests in the upstream AI-MEMORY repository.

## Probe

```bash
python tools/external_bench_ai_memory.py probe \
  --workspace s3bench \
  --project s3-agent-memory-v1
```

`AI_MEMORY_SERVER_URL` and `AI_MEMORY_AUTH_TOKEN` follow the provider's normal
host configuration. `--server-url` may override only the URL; there is
intentionally no command-line token flag.

An optional diagnostic search reports only the hit count, never memory content:

```bash
python tools/external_bench_ai_memory.py probe \
  --workspace s3bench \
  --project s3-agent-memory-v1 \
  --search-query TNDIFF
```

## Managed command preview

Generate the normal Agent Memory V1 plan with `tools/external_bench.py`, then:

```bash
python tools/external_bench_ai_memory.py command \
  --plan-file results/agent-memory-v1/ai-memory/run-1/plan.json \
  --scenario memory.cross-session.v1 \
  --workspace s3bench \
  --project s3-agent-memory-v1 \
  --phase resume \
  --harness codex
```

The adapter derives a deterministic provider-isolated workstream name from the
plan. `ai-memory` and `ai-memory+s3-integrity-gate` therefore never share the
same managed workstream.

For controlled cross-session/cross-agent cases, the adapter requires a fresh
native harness session while returning to the same durable workstream. This is
what prevents a native transcript resume from being mistaken for external-memory
success.

## Execute

Execution is deliberately explicit:

```bash
python tools/external_bench_ai_memory.py run \
  --plan-file results/agent-memory-v1/ai-memory/run-1/plan.json \
  --scenario memory.cross-session.v1 \
  --workspace s3bench \
  --project s3-agent-memory-v1 \
  --phase resume \
  --harness codex \
  --worktree /path/to/isolated/worktree \
  --prompt-file /path/to/run/prompts/memory.cross-session.v1.phase-b.md \
  --execute
```

`--prompt-file` is required for managed execution. It must be a non-empty
UTF-8 file inside the run-plan directory. The adapter sends only that phase's
prompt through stdin, without capturing stdout/stderr or persisting prompt
content. Managed process evidence records only `prompt_delivery=stdin` and
`prompt_present=true`.

Native harness arguments may be repeated with `--native-arg`. Keep them identical
between provider arms when they are controlled variables of the comparison.

## S3 Integrity Gate

The `ai-memory+s3-integrity-gate` arm uses `tools/s3_memory_gate.py` as an
operator-supplied AI-MEMORY auto-improve eval scorer. The scorer is local,
deterministic, side-effect-free, and network-free.

It receives one proposal JSON object on stdin and returns the AI-MEMORY scorer
contract on stdout:

```json
{"score_before":1.0,"score_after":1.0,"passed":true,"reason":"..."}
```

The gate verifies its own invariant registry against the current S3 checkout
before trusting it. If expected repository evidence has drifted or disappeared,
the scorer fails closed rather than applying stale assumptions.

Registered V1 invariants cover:

- balanced trit/tryte subtraction versus machine `NUMERIC_DIFFERENCE` / `TNDIFF`;
- checked non-wrapping `i64` semantics;
- `&mut` not implying automatic machine `noalias`;
- shell-free host process execution;
- the current executable FFI boundary.

Try the local safe fixture:

```bash
python tools/s3_memory_gate.py \
  < external-benchmarks/providers/ai_memory/sample-eval-proposal.json
```

`auto-improve-eval.example.toml` shows the operator-side configuration block.
It is documentation only: S3 never edits the AI-MEMORY config automatically.
