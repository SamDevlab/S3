# Control update template

Use this file as the checklist when ChatGPT/the user changes the Codex route.

## Required update steps

1. Fetch/read the current `codex-control/CURRENT.json`.
2. Increment `control_revision` by exactly 1.
3. Update `active_stage` and `active_stage_file` if the route changes.
4. Update authorization booleans explicitly; never rely on implication.
5. Replace or append concrete revision directives in `codex-control/OVERRIDES.md`.
6. If needed, add a new stage file and update `STAGE_SEQUENCE.json`.
7. Add a short entry to `CHANGELOG.md`.
8. Do not modify implementation files from the control branch update.

## Typical changes

### Pause after current stage

```json
"pause_after_current_stage": true
```

### Emergency stop

```json
"emergency_stop": true
```

### Redirect to a different stage

Set:

```json
"active_stage": "<stage id>",
"active_stage_file": "codex-control/stages/<file>.md"
```

and explain the reason/new work in `OVERRIDES.md`.

### Authorize canonical Stage1 integration

Only after Stage 08 evidence is reviewed:

```json
"canonical_stage1_mutation_authorized": true
```

### Authorize bootstrap actions

Enable each separately only when the preceding evidence is reviewed:

```json
"self_emit_authorized": true,
"stage2_authorized": true,
"stage3_authorized": true,
"t4_authorized": true
```

Do not enable all of them preemptively just because an earlier stage looks promising.
