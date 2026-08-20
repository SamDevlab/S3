# M1.94 Test Evidence

`tests/test_m194_tls_server.py` covers handshake suspension/resume, provider
identity propagation, bounded read/write, connection cleanup, missing identity
rejection, and connection overflow. Tests use a deterministic provider
fixture; they do not claim real cryptographic or native TLS evidence.

The former deadline assertion used `time.sleep(0.01)` against a 1 ms timeout
and reproduced a nondeterministic `PENDING` result. The test correction patches
the async TLS server module's monotonic clock and adds three deterministic
contracts:

```text
TIMEOUT_BEFORE_FIRST_POLL=PASS
TIMEOUT_AFTER_FRAME_OWNERSHIP=PASS
DEADLINE_NOT_EXPIRED=PASS
RESOURCE_RELEASE=PASS
EXACTLY_ONCE_CLOSE=PASS
CONNECTION_BUDGET_RELEASE=PASS
TLS_FILE=7 passed
DETERMINISTIC_REPEAT=20/20 PASS
```

The production TLS implementation was unchanged. The final campaign T4 also
reported zero failed files and completed `tests/test_m194_tls_server.py`; the
remaining campaign gate is the independent Windows per-file timeout policy.
