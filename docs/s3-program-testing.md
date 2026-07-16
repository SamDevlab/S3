# S3 Program Check Foundation

`tools/s3_program_check.py` is a small inventory and compile check for S3
programs that may become future helper, library, or experimental compiler
component candidates.

This is not self-hosting. It does not call the native backend or replace any
Python compiler component. It only records a few stable S3 programs and checks
that the current Python compiler can still compile them. Inventory entries may
also opt into hosted execution with an expected return value.

Current commands:

```text
python tools/s3_program_check.py list
python tools/s3_program_check.py check
```

Current checked programs:

- `examples/first.s3`
- `examples/simple_call.s3`
- `examples/sign.s3`
- `examples/self_hosting/assembly_renderer_stub.s3`

Conceptual gap examples under `examples/gaps/` are intentionally excluded
because they may contain pseudocode and are not part of the compile-check
inventory.

Programs under `examples/self_hosting/` may be future component stubs. They must
compile, but they do not need to implement the final component yet.

The Assembly renderer candidate stub exposes `renderer_candidate_status()` as a
minimal status API; its stub value does not mean the renderer is implemented.
`tools/compare_assembly_renderer.py --candidate-run` executes that stub through
the hosted path and confirms that `main` still returns `-1`.
`tools/s3_program_check.py check` also executes that stub because its inventory
entry declares `hosted expected return: -1`. Other inventory entries remain
compile-only until they opt into hosted execution.

The renderer candidate manifest records the same inventory path and hosted
expected return, so the general S3 program check and the renderer candidate run
share one hosted coverage contract for the stub.

The same stub is also included in golden inspect coverage as
`assembly_renderer_stub`, which records its current IR and Assembly outputs
without treating it as a real renderer.

The stub also exposes scalar capability functions for the renderer subset:
`renderer_supported_directive_count()` and
`renderer_supported_opcode_count()`. They report the current subset manifest
counts only; `compare_assembly_renderer.py --check` remains blocked.

It also exposes scalar ID functions for each supported directive and opcode.
Those IDs are deterministic constants that follow the subset manifest order;
they are not Assembly rendering.
