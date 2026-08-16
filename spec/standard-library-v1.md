# S3 Standard Library v1

## Module manifest

| Module | Exports | Capability |
| --- | --- | --- |
| `s3.v1.collections` | `new_map`, `put_map`, `get_map`, `new_set`, `add_set` | none |
| `s3.v1.core` | `clamp_tryte`, `identity_i64` | none |
| `s3.v1.host` | `grant`, `open`, `active`, `invoke` | `resource` |
| `s3.v1.io` | `kind`, `close_resource` | `resource` |
| `s3.v1.text` | `from_static`, `length` | none |

The manifest is versioned and deterministic. The compiler accepts an explicit
selection of known module IDs and rejects unsupported versions or unknown
IDs. Module paths are implementation details of the manifest, not a second
identity mechanism.

## Capability boundary

The `resource` capability is declared only by host-facing modules. A module
declaration does not mint authority. `grant`, `open`, `active`, `invoke`, and
`close_resource` operate on explicit capability, handle, and borrow values
from the M1.43 resource boundary. There is no ambient host access.

## Compatibility

The `s3.v1` module IDs and exports are the v1 contract. Incompatible changes
must use a new versioned namespace. Additive changes require manifest and
specification updates. Wildcard imports, implicit capability imports, package
registry resolution, and locale-dependent behavior are not defined here.

## Execution

The same source modules are accepted by the hosted compiler/IR emulator and
the Linux x86-64 native backend. The M1.44 proof covers selected core and
host/io modules at O0 and O1, plus cross-module text and collection execution.
