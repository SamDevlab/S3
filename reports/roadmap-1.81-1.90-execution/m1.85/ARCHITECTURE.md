# M1.85 Architecture

M1.85 provides a bounded HTTP/1.1 client over an explicit raw transport boundary. The default `SocketHTTPTransport` opens real TCP connections and wraps HTTPS connections with `ssl.create_default_context()`. A supplied TLS context is accepted only when certificate verification is `CERT_REQUIRED` and hostname checking is enabled; there is no insecure HTTPS fallback.

`BoundedHTTPClient` supports GET and POST with absolute HTTP(S) URLs, bounded request/header/body sizes, connection-close framing, and a single monotonic request deadline. Connect, TLS handshake, send, and every receive step consume the same deadline budget rather than receiving a fresh timeout window. Request target/header CR/LF injection, URL credentials, invalid ports, non-ASCII V1 request headers/hosts, duplicate/reserved framing headers, oversized headers, and oversized bodies fail closed before or at the transport boundary. Response reads stop at a hard transport byte budget.

The response parser accepts HTTP/1.1 with bounded unique ASCII headers and exact non-negative `Content-Length`. Transfer-Encoding/chunked remains intentionally unsupported in V1 and fails closed rather than being parsed incompletely. Malformed status/framing, header overflow, and body overflow are explicit failures.

`LocalHTTPFixtures`/`LocalHTTPClient` remain deterministic test adapters behind the same bounded parser. Separate loopback TCP coverage proves that the production client is not merely an in-memory fixture parser. Public internet access is not required by correctness tests.
