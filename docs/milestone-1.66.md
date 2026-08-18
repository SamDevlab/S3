# Milestone 1.66 - Cross-Platform OS Services V1

## Architecture status

M1.66 adds `CrossPlatformOSServices`, a bounded provider using an explicit
service root, explicit argv/environment snapshots, deterministic directory
ordering, and shell-free process invocation. `HostPath` is a relative project
path; host-specific resolution is performed only inside the provider and paths
escaping its root are rejected.

Expected file, directory, process, and close failures are returned as explicit
`Result` values with a typed `HostErrorCode`. Optional environment values use
`Option`. `OwnedTextFile` closes deterministically and idempotently and never
relies on a finalizer for correctness. Non-zero child exit is a process result,
not a provider failure. Process waits are explicitly bounded to 30 seconds and
malformed command arguments are rejected before process creation.

## Compatibility and safety

The existing Linux host-service provider and scoped resource registry remain
unchanged. No ambient handles, absolute paths in semantic identity, shell
execution, GC finalizers, or hidden retry loops were added. The same provider
contract can be exercised on Linux or Windows using temporary roots.

## Out of scope

ACL policy, filesystem watchers, async I/O, platform-specific GUI APIs, and
unbounded directory/process streaming remain out of scope.

## Implementation status, public surface, and dependency

COMPLETE for the hosted `HostPath`, `OwnedTextFile`, directory, environment,
argv, and shell-free process provider. M1.67 consumes this explicit
OS/resource boundary. No additional native certification is claimed here.
