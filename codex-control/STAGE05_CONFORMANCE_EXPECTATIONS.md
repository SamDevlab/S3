# Stage05 strict conformance expectations

Purpose: map the authoritative `verify_stage1_semantic_conformance_v2.py` errors to one Stage05 repair owner after valid call parsing is restored.

This document is read-only guidance. It does not authorize foreign calls, arrays, Stage06, canonical mutation, SELF_EMIT, Stage2, Stage3, or T4.

## Call verifier order

The verifier first maps ordinary `I/V/O/R` semantic identity and only then checks calls. Therefore an `A` mismatch may be downstream of a missing value/result mapping. Fix the first verifier error only.

## Exact Stage05 call mismatch map

```text
candidate stream fails internal S3IR2 v2 verification
  OWNER=STREAM_STRUCTURE
  ACTION=fix first internal stream error before semantic call comparison

instruction <n> semantic shape mismatch
  OWNER=CALL_INSTRUCTION_SHAPE if this is the call instruction
  CHECK=opcode 14, result_count, operand_count, ordinal

result edge count mismatch for instruction <id>
result ordinal mismatch for instruction <id>
  OWNER=R_RESULT_EDGE
  ACTION=repair call result definition before C/A

cannot map operand edge [...]
missing mapped operand edge for expected [...]
  OWNER=O_OPERAND_OR_VALUE_MAPPING
  ACTION=repair mapped argument/result identity or O ordinal before A

missing call record for expected instruction <id>
  OWNER=C_RECORD_ATTACHMENT
  ACTION=emit C for the mapped CALL instruction; do not invent a second instruction id

call semantic metadata mismatch for instruction <id>
  OWNER=C_METADATA
  CHECK=callee_kind, mapped callee_function_id, argument_count, result_count

call source identity mismatch for '<name>'
  OWNER=C_SOURCE_SPAN
  CHECK=exact ASCII callee_name_start/callee_name_length

cannot map call argument edge [...]
  OWNER=VALUE_MAPPING_BEFORE_A
  ACTION=the expected argument value is not mapped yet; inspect V/R/O identity before patching A

missing mapped call argument for expected [...]
  OWNER=A_ARGUMENT_EDGE
  CHECK=instruction id, argument ordinal, mapped semantic value id
```

## Required invariants for an internal call

For `helper(1)`:

- CALL `I` opcode is `14`;
- CALL `O` operands are in semantic/source order;
- returned call value has exactly one `R` definition when applicable;
- `C.callee_kind = 1` for internal;
- `C.callee_function_id` maps to the already-emitted helper function;
- `C` source span slices the exact text `helper`;
- `C.argument_count = 1`;
- `C.result_count` matches the function result;
- `A 0` points to the same mapped semantic argument value as CALL `O 0`;
- call result identity is reused by enclosing return/local lowering rather than copied into an unrelated logical identity.

Candidate logical IDs may differ from the hosted oracle. Physical scratch/pool slots are not semantic identity.

## Fast repair policy

After parser validity is restored:

1. run strict conformance immediately on `internal_one_arg_call.s3`;
2. preserve verifier JSON;
3. take `errors[0]` only;
4. use the map above to choose one owner;
5. repair one owner;
6. regenerate/check/build once;
7. rerun the same fixture before expanding.

A `Z 7` stream with verifier errors is not PASS. A strict conformance PASS with `Z 7` is the first internal-call closure target.
