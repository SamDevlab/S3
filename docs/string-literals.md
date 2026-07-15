# String Literals

Double-quoted string literals are reserved S3 syntax.

They are not runtime values yet, and the language does not have a `string` type.
When a string literal appears in source code, the front-end reports a
deterministic diagnostic instead of treating it as generic invalid syntax.
Escapes are only scanned enough to find the closing quote; they are not decoded
or assigned semantics.

Future string support will depend on a minimal string representation plus
arrays or buffers, records, and deterministic formatting helpers. This document
only records the current reservation; it does not define string semantics.
