# S3 Program Check Foundation

`tools/s3_program_check.py` is a small inventory and compile check for S3
programs that may become future helper, library, or experimental compiler
component candidates.

This is not self-hosting. It does not execute programs, call the native backend,
or replace any Python compiler component. It only records a few stable S3
programs and checks that the current Python compiler can still compile them.

Current commands:

```text
python tools/s3_program_check.py list
python tools/s3_program_check.py check
```

Current checked programs:

- `examples/first.s3`
- `examples/simple_call.s3`
- `examples/sign.s3`

Conceptual gap examples under `examples/gaps/` are intentionally excluded
because they may contain pseudocode and are not part of the compile-check
inventory.
