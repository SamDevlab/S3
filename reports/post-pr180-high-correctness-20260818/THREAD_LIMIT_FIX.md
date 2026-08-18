# M1.69 Thread Limit Fix

Base: `76030c5d5428e47f6839c219c4930db4cb1862d8`

Fix commit: `1223fd435fa724b01eb19123cbdd079589350895`

`ThreadRuntime.spawn` now reserves an active slot under the existing lock
before consuming an `OwnedValue`, constructing a thread, or registering a
handle. The reservation is released exactly once when the worker completes,
or rolled back on ownership failure, construction failure, or start failure.
`active_count` reports the reserved/running execution slots, so completed but
unjoined handles do not retain capacity and the observable count remains
bounded by `max_active`.

Focused certification:

- atomic concurrent admission: PASS
- concurrent `max_active=1` limit: PASS
- `RESOURCE_LIMIT` preserves an unmoved `OwnedValue`: PASS
- failed owned move does not leak capacity: PASS
- thread start failure rolls back capacity: PASS
- completed unjoined worker releases capacity: PASS
- existing `tests/test_m169_threads.py`: PASS
- T2 M1.69: 5 files passed
- M1.70 impact: NOT_REQUIRED by the project impact map
