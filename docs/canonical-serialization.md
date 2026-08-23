# Canonical Debug Serialization

`bootstrap.s3.canonical_serialization` provides a bounded reference encoding
for future AST/IR debug and differential artifacts. It accepts only explicit
JSON-shaped values, sorts object keys, preserves UTF-8, rejects non-finite
numbers and unsupported host objects, and terminates with one newline.

`serialize_debug` adds a required schema and version envelope. Both functions
measure the encoded UTF-8 bytes and fail before returning a value that exceeds
the configured bound. They do not replace the versioned `serialize_ir`
artifact format.
