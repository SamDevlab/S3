# ChatGPT Stage1 snapshot review — 2026-09-04

Source snapshot commit: `c0fb839f730706065e4764c6be191d118ca0c306`

Candidate reviewed: `eeddc241c168b586f0e72b36ad1fbb93261b6031a56e23b7e22f8b6a4e1cc583`

Canonical reviewed: `44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb`, 225699 bytes.

## 1. Current F24 milestone

Do not interrupt the currently running local milestone merely because the last emitted function record remains `F=10` while worker CPU continues increasing.

The previous measured run spent roughly 5362 seconds between F10 and F11. The current behavior is therefore consistent with a known expensive prefix region and is not, by itself, evidence of deadlock.

No candidate/source change from this review branch should be copied into the campaign worktree until that running milestone has reached a terminal state.

## 2. Terminal-match semantic fix

Static review of the current candidate supports the new shared terminal-result behavior.

The candidate has a shared continuation protocol in which:

- kind 2 = terminal continuation;
- kind 3 = continuation with explicit successor block.

The all-terminal three-arm match path now returns kind 2, while a match containing fallthrough continues to return kind 3. `scan_program` already consumes kind 2 by decoding the returned next-id/cursor and marking the function as having returned.

The regression fixture is generic (`classify` followed by `after`) and does not depend on the canonical function name `emit_ir_return`.

No further semantic candidate edit is justified from static evidence at this point. Changing semantic code before the running F24 result would mix provenance and reduce confidence.

## 3. What F24 means here

In the protected canonical source, `emit_ir_return` is immediately followed by `emit_error`.

Therefore the current F24 milestone is a particularly clean boundary test: if F24 is emitted, the new terminal-match result propagated across the `emit_ir_return` function boundary and the next function header was reached.

This is still milestone evidence, not S1.2 qualification.

## 4. Confirmed probe-harness correctness defect

`tools/stage1_fast_probe.py` currently has two related truthfulness problems:

1. `qualification_complete` is set to `stop_after_f is None`, even when `scan_program` itself returns a negative failure result.
2. `_canonical_diagnostic()` interprets absence of `Z` as canonical stream incompleteness, even though this harness directly invokes `scan_program`; `Z` is emitted only by the candidate `main` finalization path.

The current diagnostic also guesses a semantic RULE_ID from the mere presence of T records. That is not sufficient evidence for the first semantic divergence.

These defects can produce a misleading final diagnosis after a multi-hour run.

## 5. Proposed patch

Apply `review_snapshot/proposed/stage1-fast-probe-truthfulness.patch` to the campaign checkout only after the currently running milestone terminates.

The patch:

- captures the actual return value of `scan_program`;
- records `scan_program_completed` explicitly;
- makes `qualification_complete` depend on successful scanner completion;
- marks `Z` as not authoritative in direct-`scan_program` mode;
- stops guessing a semantic rule from aggregate record counts;
- adds regression coverage for successful direct completion without Z and for negative scanner return;
- reports scanner completion state in milestone payloads.

It intentionally does **not** change Stage1 candidate semantics.

## 6. First test after applying the patch

Run one foreground local gate, with no canonical replay:

```powershell
python -m pytest -q tests/test_stage1_fast_probe.py tests/test_stage1_semantic_event_spine.py::test_candidate_v3_all_terminal_match_preserves_function_boundary; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python -m compileall -q tools; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; git diff --check
```

Expected:

```text
FAST_PROBE_TRUTHFULNESS=PASS
TERMINAL_MATCH_BOUNDARY=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
CANONICAL_REPLAY=NO
```

## 7. Decision after the running milestone

If the current candidate reaches F24:

```text
DEVELOPMENT_FRONTIER_F=24
FULL_QUALIFICATION_FRONTIER_F=23
```

Do not run another full canonical immediately. Apply the probe truthfulness patch, run the local gate above, then diagnose the next frontier locally.

If the current candidate returns F23:

Do not rerun the milestone. Apply the probe patch and use bounded local diagnostics to determine the exact next first divergence.

If it returns F<23:

Treat provenance/regression as the first problem before making another semantic change.

## 8. Adjacent repository audit

The local snapshot already adds `selfhost/**` and `stdlib/**` to the principal test-workflow path filters. Keep that change.

Do not migrate the current name-based `pytest -k` grouping to markers until node-id parity and complete marker coverage are proven.

The assert/python-O audit remains worthwhile but is independent of the F24 semantic boundary and should not trigger an expensive canonical replay.

## Review disposition

```text
CURRENT_CANDIDATE_SEMANTIC_FIX=STATICALLY_APPROVED_FOR_CURRENT_F24_MILESTONE
NEW_CANDIDATE_SEMANTIC_EDIT_FROM_REVIEW=NONE_JUSTIFIED_YET
PROBE_HARNESS_TRUTHFULNESS_FIX=RECOMMENDED
CURRENT_RUNNING_MILESTONE=DO_NOT_INTERRUPT
NEXT_EXPENSIVE_REPLAY=NOT_AUTHORIZED_BY_THIS_REVIEW
```
