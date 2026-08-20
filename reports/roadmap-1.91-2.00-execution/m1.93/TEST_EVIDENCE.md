# M1.93 Test Evidence

`tests/test_m193_http_server.py` covers partial headers and bodies, complete
request framing, response serialization, duplicate framing headers, rejected
chunked transfer encoding, body limits, connection limits, and close behavior.
It also drives `LoopbackHTTPServer` through an actual `127.0.0.1` TCP socket,
verifies bounded response chunking and deterministic peer close, and verifies
the one-global-deadline timeout path.

The fixture is local-only and does not use a public socket or external service.
No benchmark or native claim is made by this checkpoint.
