# Codex fast path — autonomous overnight Stage1 → Stage2 → Stage3

Read, in order:

```text
codex-control/CURRENT.json
codex-control/OVERRIDES.md
codex-control/RECOVERY_REV33_PROVENANCE_GRAPH.md
codex-control/OVERNIGHT_REV34_STAGE1_STAGE2_STAGE3.md
```

Expected control:

```text
CONTROL_REVISION=34
ACTIVE_STAGE=OVERNIGHT_GATED_STAGE1_STAGE2_STAGE3
```

## Mandatory first action

Finish revision-33 provenance analysis before reapplying anything.

Then, only if the provenance graph gives a safe ordered plan:

```text
Stage1 minimal reapplication waves
→ validate each wave
→ narrow repairs only
→ Stage1 closure
→ SELF_EMIT
→ Stage2
→ Stage2 compiles Stage3
→ Stage2↔Stage3 equality/determinism
→ correctness tests
→ benchmark
→ final report
→ shutdown Windows after 60s
```

## Critical rules

- Original dirty worktree is immutable evidence.
- Use a dedicated overnight branch from exact d67da9e.
- Missing evidence is never PASS.
- Hosted oracle is not native Stage1 proof.
- Stage2 must be produced by actual SELF_EMIT.
- Stage3 must be produced by actual Stage2.
- Do not invent equality rules.
- Benchmark comes last.
- No PR merge.
- No force push.
- Stop at first non-narrow/unprovable blocker.
- Write final report before shutdown.

Full campaign rules are in `OVERNIGHT_REV34_STAGE1_STAGE2_STAGE3.md`.
