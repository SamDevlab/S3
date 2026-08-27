# Live overrides

CONTROL_REVISION: 1

No emergency reroute is active.

Current direction:

- Start from Stage 01 and follow the numbered stage sequence.
- Treat S3IR2 v2 as frozen.
- Work on candidate transforms/artifacts first; do not overwrite canonical `selfhost/compiler/s3c_stage1.s3` while `canonical_stage1_mutation_authorized=false`.
- Reuse the semantic handoff from PR #270 rather than redesigning the protocol.
- The v1 patch/probe files are prototypes/history only; new implementation targets v2.
- Local Linux x86-64 evidence is authoritative while GitHub Actions keeps failing before exposing job steps.
- Do not initiate SELF_EMIT, Stage2, Stage3, or T4 while their authorization flags in `CURRENT.json` are false.
- If the control-branch fetch/read fails, Codex may finish the currently running atomic command, but must not enter a new numbered stage, create an implementation commit, mutate canonical Stage1, or cross a promotion/bootstrap gate until the live control revision can be read again.

If this file is modified at a later control revision, newer instructions here supersede the matching stage-path details in the megaprompt, but they do not silently relax fail-closed evidence requirements.
