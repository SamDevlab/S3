# M1.43 Scoped Host Resources

## 1. Closed source vocabulary

Resource values are not generic values and are not public integers:

    capability: host_capability = host_capability_grant(1)
    mut handle: resource_handle = resource_open(capability)

The accepted fixture kind IDs are:

| ID | Kind |
| ---: | --- |
| 1 | file |
| 2 | process |
| 3 | socket |

The IDs are a deterministic fixture contract, not a promise that the native
runtime opens an operating-system object.

## 2. Lifecycle

The source operations are:

    resource_is_open(&handle)
    resource_kind(&handle)
    resource_invoke(&handle, argument)
    discard resource_close(&mut handle)

resource_is_open returns -1 for an active handle and 0 otherwise. resource_kind
and resource_invoke require an active handle. resource_close requires a
mutable reference, removes the active resource, and writes the owner cell to
zero. A zero value is never an active handle.

The hosted registry additionally provides ResourceScope, which tracks opens
and closes live handles in reverse order on normal or exceptional exit.

## 3. Capability policy

Capabilities are issued by a ResourceRegistry only after a provider for the
requested ResourceKind is registered. A token from one registry cannot open a
resource in another registry. A provider must implement open, invoke, and
close, and invoke must return a DynamicValue.

The source fixture uses the same closed kind policy without ambient provider
lookup. An invalid kind, unavailable capability, closed handle, or active-slot
limit is a deterministic resource failure.

## 4. Determinism and native layout

Hosted handles use a private (slot, generation) identity. The source/IR
fixture encodes kind, one-based slot, and generation into an opaque i64 cell.
The native fixture has three zero-initialized slots and three generation cells.
Slots are selected from the lowest free index. Reopening a slot increments its
generation, so a stale handle cannot become current by slot reuse.

The native entry points are private runtime symbols. The Assembly verifier
requires resource references to target i64, and the native emitter passes
references as owner-cell pointers under the existing dynamic-call ABI.

## 5. Failure boundary

Type misuse, wrong mutability, borrow conflicts, stale references, and
malformed artifacts remain semantic or verifier failures. Provider boundary
errors are represented by ResourceError subclasses in hosted code and by
deterministic native runtime failure categories in the bounded fixture.
Application-level expected statuses must continue to use explicit nominal
result values under the M1.42 contract.

## 6. Non-goals

This specification does not add generic resource types, implicit cleanup for
all values, garbage collection, threads, POSIX descriptor ownership, real
socket/process execution, or unrestricted host access.
