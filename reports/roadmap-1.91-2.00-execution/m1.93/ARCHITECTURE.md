# M1.93 Architecture: Streaming HTTP Server Boundary

M1.93 adds a transport-neutral incremental HTTP/1.1 server session registry.
`IncrementalHTTPRequestParser` retains only a bounded header/body buffer and
emits complete `HTTPRequest` frames after `Content-Length` validation.
`StreamingHTTPServer` bounds active connections and delegates bytes to one
parser per connection, so socket ownership remains outside the protocol
layer.

The parser rejects duplicate or non-decimal `Content-Length`, all
`Transfer-Encoding`, unsafe header bytes, oversized headers/bodies, and frame
queue overflow. Responses always carry one generated `Content-Length` and
`Connection: close`; caller-provided framing headers are rejected.
