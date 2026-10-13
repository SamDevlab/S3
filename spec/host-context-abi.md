# Experimental Host Context Boundary (V6)

Status: **design and compatibility inventory; not a stable ABI**.

This document records the host-resource boundary present during V6 and the
gaps that must be closed before a cross-backend provider ABI can be claimed.
The existing source contract in `scoped-host-resources.md` remains unchanged.

## Existing source surface

The source/IR surface has six fixed operations:

| Operation | Current source-level result |
| --- | --- |
| `host_capability_grant(i64)` | `host_capability` |
| `resource_open(host_capability)` | `resource_handle` |
| `resource_is_open(&resource_handle)` | `trit` (`-1` open, `0` closed/unknown) |
| `resource_kind(&resource_handle)` | `i64` kind ID |
| `resource_invoke(&resource_handle, i64)` | `tryte` (fixture returns `0`) |
| `resource_close(&mut resource_handle)` | `tryte` (`0`), closes and clears owner cell |

Kind IDs 1 through 3 are the existing deterministic file/process/socket
**fixture labels**. They do not open files, spawn processes, or create sockets.
`resource_invoke` is a fixture operation and is not a general typed provider
call. Source code can request a fixture capability by kind; this is not an
authorization mechanism for real host access and must not be reused as one.

## Hosted execution

`HostExecutionContext` is an execution-local object shared by the IR and
Assembly emulators. An execution creates one when the caller does not provide
one; a caller may explicitly pass one. Its current `SourceResourceRuntime` is
bounded to three active slots, chooses the lowest free slot, increments a
generation on reuse, and represents an invalid/closed source handle as zero.
Hosted stale or unknown handles fail through typed `ResourceError` subclasses;
`resource_is_open` reports false rather than raising.

The separate Python `ResourceRegistry` is a provider-oriented host API. It
supports registered `ResourceProvider` implementations, registry-scoped
capability tokens, generation-checked handles, and `ResourceScope` cleanup.
It is not currently the implementation behind the six source builtins. In
particular, the source `i64` invocation signature cannot expose the registry's
general `DynamicValue` argument/result contract without an explicit language
and IR design change.

## Native and QBE status

The current S3 x86-64 runtime stores fixture slots and generations in
process-global runtime data. QBE x86-64 can call the same fixture symbols. This
establishes a shared fixture behavior, not a per-execution native context. It
does not qualify concurrent entry into one loaded artifact, real host
providers, automatic cleanup at program exit, or provider errors across
backends. The Assembly and IR emulators use execution-local hosted state, so
their ownership model is not yet identical to the native fixture's storage
model.

QBE ARM64 and RISC-V status must be reported independently. A QBE target's
ability to emit code is not evidence that this runtime boundary executes there.

## Requirements for a future versioned ABI

Before calling this a provider ABI, a follow-up design must define and test:

- context creation, ownership, destruction, and cleanup on success and error;
- host-issued capability policy, revocation, permitted operations, and denial;
- opaque logical handles, invalid values, generation/reuse, and cross-context
  rejection without exposing host pointers to S3 code;
- provider `open`, typed invocation arguments/results, close, and error mapping;
- an explicit context boundary for every native target, with pointer width,
  alignment, calling convention, and threading assumptions stated;
- equivalent observable behavior for IR, Assembly, S3 x86-64, and each
  qualified QBE target.

One viable shape is a host-owned opaque context pointer passed at the program
entry boundary and threaded as hidden state to resource calls. It remains a
design option, not the current ABI. A process-global context is not an
acceptable substitute for execution-local ownership or concurrency safety.

## V6 claim boundary

Until those requirements have executable evidence, report the source resource
fixture separately from the host-services registry, and report hosted,
S3-native, QBE x86-64, QBE ARM64, and QBE RISC-V results separately. Keep the
default compiler as Python and the default native backend as S3 x86-64.
