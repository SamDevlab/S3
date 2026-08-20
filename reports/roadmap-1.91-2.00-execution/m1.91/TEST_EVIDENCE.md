# M1.91 Test Evidence

Focused proof executed on the campaign worktree:

```text
python -m pytest -q tests/test_m191_async_select.py
5 passed

python -m pytest -q tests/test_m191_async_select.py tests/test_m181_async_ir.py tests/test_m182_futures_modules_generics.py tests/test_m176_async_channels.py tests/test_m171_async_core.py
all selected tests passed

python -m compileall -q bootstrap/s3
PASS
```

The focused tests cover:

- parser and executable IR materialization;
- deterministic source-order selection when multiple candidates are ready;
- suspension and resume through a nested select-arm await;
- Future ownership consumption and cancellation cleanup;
- double-consumption and arity rejection;
- bounded deterministic channel select and empty/over-arity failure.

No benchmark was run. No native Linux claim is made by this focused evidence.
The campaign-level T0/T1/T2/T3 and final T4 gates remain outstanding until
the complete M1.91-M2.00 sequence is validated.
