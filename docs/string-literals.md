# String Literals

Double-quoted string literals are reserved S3 syntax and are now parsed as
static front-end expressions.

They are not runtime values yet, and the language does not have a `string` type.
When a string literal appears in source code, semantic analysis reports a
deterministic runtime-unsupported diagnostic before IR, Assembly, or backend
generation. Completed literals are no longer treated as generic parse errors.
Escapes are only scanned enough to find the closing quote; they are not decoded
or assigned semantics.

Future string support will depend on a minimal string representation plus
arrays or buffers and deterministic formatting helpers. This document records
the current static-literal foundation; it does not define runtime string
semantics.
