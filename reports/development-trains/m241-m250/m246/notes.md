# M2.46 Async and Network Native Soak Hardening

## WHY_NOW

The async and network layers already had bounded individual contracts. M2.46
checks that their limits, ownership, cancellation, transport framing, and
cleanup continue to hold when the same workload is repeated across a bounded
soak rather than a single example.

## ARCHITECTURAL_DECISION

Keep the existing provider-neutral async contracts and make cleanup explicit at
the executor boundary. Terminal task collection now removes reactor
registrations owned by those tasks, and executor shutdown clears all remaining
reactor readiness state. No unbounded retry loop, indefinite uptime claim, or
implicit network provider was introduced.

## IMPLEMENTATION_SUMMARY

- Added reactor-registration cleanup during task reaping and executor close.
- Added a bounded repeated workload covering tasks, timers, channels,
  backpressure, cancellation, network handles, HTTP/1 loopback, HTTP/2 stream
  state, and TLS handshake/read/write/close progress.
- Preserved bounded body windows, one-shot cleanup, and read/write limits.
- Added M2.46 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- `git diff --check`: PASS
- Focused Windows cross-layer matrix: 53 passed.
- T2 M2.46 at source HEAD
  `208ad105fe7bbbe016f2b925b3e3a54751624d88`: 3 selected, 3 passed, 0
  failed, 0 timed out.
- T3 M2.46 shard at the same source HEAD: 10 selected, 10 passed, 0 failed,
  0 timed out.
- Linux x86-64 remote matrix at the same source HEAD: 53 passed, exit 0.

## TLS_AND_PROVIDER_SCOPE

The TLS state machine was exercised through bounded want-read, ready, I/O,
close, and cancellation transitions. Certificate and hostname validation
remain mandatory. The async TLS layer remains provider-neutral; no native TLS
provider is silently substituted, and no indefinite network soak is claimed.

## BENCHMARK_RELEVANCE

None. This milestone certifies bounded correctness, cleanup, and transport
behavior; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

The Linux proof is a bounded focused matrix, not an uptime guarantee. Native
TLS provider wiring and long-duration service operation remain separate
concerns.
