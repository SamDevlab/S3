# PR #182 Corrective Campaign Report

Campaign: `S3-PR182-CORRECTION-20260819`

## Provenance

- PR: #182
- Base main: `cbfd833437dac7f3b6083b3aa28a6653cbe149ca`
- Reviewed pre-correction head: `46a6d7dc86a7fe98c969e59b711a6e490bf0183c`
- Main corrective semantic/code commit: `9f9eaa5937c81cd50929a7d5ed366b68327022ad`
- Async front-end follow-up: `c33d0d66a4aba1b899f58900352eb9a79a3bb039`
- Follow-up reason: the first contextual-marker implementation replaced top-level `async` with spaces, which could be interpreted by the V0.6 indentation lexer as indentation. The follow-up removes contextual marker prefixes and maps parser offsets deterministically back to original async source locations.
- Remote branch movement has remained normal fast-forward only; no force push, direct main push, or merge.

## Review findings addressed

### M1.71 source/compiler BLOCKER

Implemented a bounded compiler front-end extension for source-visible `async fn` and `await direct_call()` syntax. It delegates the stable core grammar to the existing parser, retains original async source locations plus deterministic transformed-offset bindings, runs explicit async semantic validation, and emits `AsyncStateMachinePlan` compiler metadata.

V1 intentionally requires immediate await of async calls and rejects generic async functions, stored/general Future expressions, multi-file async rewriting, and native resumable-frame codegen. The hosted execution path uses the existing direct-call IR for an immediately-awaited call while the compiler retains the explicit suspension plan. Native resumable IR/backend execution is not claimed and is planned as M1.81 work after PR #182 closure.

### M1.71 re-entrant poll HIGH

`AsyncFuture.poll()` now fails closed when the frame is already `RUNNING`. Re-entrant cancellation is also rejected.

### M1.72 join-result HIGH

`TaskHandle` retains the exact terminal `Poll` produced by its owned future. `join()` consumes and returns that exact result once, preserving success values and original failures. Cooperative cancellation stores an explicit cancellation terminal result for later join.

### M1.74 pending-resource HIGH

The resource future retains the pending resource identity. Completion must return that exact resource. A replacement resource fails closed; the replacement is closed immediately and frame failure drops the original pending resource. Successful completion creates the handle from the value moved out of the frame-owned slot.

### M1.79 extraction-bound HIGH

Registry extraction prevalidates all members before creating/writing the destination tree, rejects non-regular members and duplicate canonical output paths, enforces per-member uncompressed size and cumulative extracted-byte limits, and performs bounded reads checked against TarInfo size.

## Added focused correction coverage

`tests/test_pr182_corrections.py` covers:

- source `async fn` / `await` compilation and deterministic plans;
- missing-await and sync-await diagnostics;
- ordinary reference live across await rejection;
- re-entrant future polling;
- TaskHandle success/failure/cancellation join preservation;
- PendingResource exact transfer and replacement fail-closed behavior;
- registry per-member/cumulative uncompressed limits and duplicate paths.

## Test execution status

GitHub Actions is unavailable/disabled for this repository and the connected GitHub tool does not provide a repository execution environment. Therefore the correction is source-reviewed remotely but the focused pytest/compileall gate has not been executed here.

Required local focused gate before changing PR #182 from Draft to merge-ready:

```text
python -m compileall bootstrap/s3
python -m pytest -q tests/test_m171_async_core.py tests/test_pr182_corrections.py tests/test_m172_structured_concurrency.py tests/test_m174_async_network.py tests/test_m179_registry_client.py tests/test_m180_toolchain_distribution.py tests/test_m165_windows_x86_64_backend.py
```

Use a unique `--basetemp` locally if the historical Windows pytest temp-directory permission issue reappears. Do not restart the global T4 merely for publication ceremony. If the focused gate finds a real cross-subsystem regression, expand only according to the impact map.

## Preserved truth

- Original raw T4 remains 348 selected / 291 passed / 35 failed / 22 timed out / 0 skipped / 0 restarts.
- Linux AArch64 remains structural only; execution certification deferred.
- macOS ARM64 remains structural only; execution certification deferred.
- M1.79 remains an offline/local read-only registry client; HTTP/HTTPS transport and publishing are not claimed.
- Instruction limit remains 100000.
- No GC, public raw pointers, JIT, tag, release, branch deletion, M1.81 implementation, shutdown, or reboot was introduced/executed.

## Current classification

`PR182_CORRECTIONS_IMPLEMENTED_PENDING_LOCAL_FOCUSED_TESTS`

`READY_FOR_MERGE=NO_PENDING_LOCAL_FOCUSED_TESTS`
