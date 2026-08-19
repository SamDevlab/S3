# M1.85 Architecture

M1.85 defines a bounded HTTP/1.1 client over local, in-memory fixtures only.
The transport accepts exact fixture URLs and returns raw response bytes; it
does not import or invoke DNS, sockets, proxies, or external network services.

The parser requires a valid HTTP/1.1 status line, unique bounded headers, and
an exact non-negative `Content-Length`. Chunked encoding, conflicting framing,
malformed headers, oversized headers, oversized bodies, unsupported methods,
and unknown fixtures fail closed. Responses are immutable values owned by the
returned Future.

TLS, remote transport, retries, redirects, and authentication are outside
M1.85 and remain unimplemented until the content-addressed transport work in
M1.86.
