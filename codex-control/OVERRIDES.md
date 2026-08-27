# Live overrides

CONTROL_REVISION: 20

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- The parser/call-close fixes are retained; simple internal call execution is now reported `RC=0` with `C` and ordered `A` emitted.
- The observed final mask for that simple call is `Z 3`, not `Z 7`; therefore S3 is not yet closed/claimed.
- Do not infer from `Z 3` alone that the mask-emission code is wrong.
- A real multi-argument bug was found: the comma branch advanced the cursor twice and skipped the next argument. The localized cursor repair is already in an in-flight native build.
- Finish that exact build before any new edit/build.
- Read `codex-control/STAGE05_CALL_MATRIX_BEFORE_ARRAYS.md` before broadening.

## Current atomic task

When the in-flight build terminates, reuse the same binary for:

```text
zero_arg_internal_call.s3
internal_one_arg_call.s3
ordered_two_arg_internal_call.s3
```

Record for each:

```text
EXIT_CODE=
Z_MASK=
CALL_OPCODE=
C_RECORD_PRESENT=
A_RECORD_COUNT=
A_VALUE_IDS_IN_SOURCE_ORDER=
O_RECORD_COUNT=
O_VALUE_IDS_IN_SOURCE_ORDER=
R_RECORD_COUNT=
PARSE_OK_FINAL=
```

Stop at the first valid-call regression to `Z 0` or malformed call data.

## Gate before arrays

If zero/one/two-argument calls structurally pass, run the current **stage-local** strict Stage05 conformance gate on the one-argument fixture before editing arrays or foreign calls.

Decision:

```text
STRICT_CONFORMANCE=FAIL
  -> preserve verifier JSON
  -> consume errors[0] only
  -> fix one semantic owner

STRICT_CONFORMANCE=PASS and Z_MASK=3
  -> inspect only the candidate Stage05/S3 completeness predicate
  -> identify which required S3 condition is still unset
  -> do not force bit 4 merely because C/A exist

STRICT_CONFORMANCE=PASS and Z_MASK=7
  -> first internal-call S3 proof closed
  -> continue same-binary internal call regression matrix
```

The frozen hosted oracle uses a full-completeness mask for its own final stream; the paired Stage04/Stage05 campaign has stage-local partial masks. Use the current worktree's stage-local verifier/gate and report exactly which command/verifier produced the result.

## Internal-call order after first strict PASS

```text
zero arg
one arg
ordered two arg
nested call
call result reuse
unresolved callee fail-closed
```

Only after the internal call matrix is stable may a later control revision unlock foreign calls and arrays/indexing.

## Do not reopen / do not broaden

Do not spend time on:

- the old special-open/right-paren parser traces unless a regression directly points there;
- `stage05_open_kind > 0` truth experiments;
- SSH/Linux/Python/cc requalification;
- Stage04 expression matrix;
- historical capacity;
- arrays right now;
- foreign calls right now;
- Stage06 or later.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.
