# M1.66 Architecture Preflight

## Existing authority

`LinuxHostServices` already has explicit argv/environment snapshots, shell-free
processes, text file operations, and deterministic timeout mapping. The
`ResourceRegistry`/`ResourceScope` already owns opaque resources and closes
them in reverse order.

## Selected implementation

Add a portable provider rather than duplicating Linux and Windows logic. The
provider accepts an explicit filesystem root and a relative `HostPath`, returns
typed `Result` errors for expected failures, returns `Option` for absent
environment variables, sorts directory entries, and exposes an owned text file
whose close is explicit and idempotent.

## Boundary

Host path spelling and process executable resolution remain host-specific at
the provider boundary. Project identity never includes an absolute resolved
path. Existing capability enforcement remains the caller's explicit registry
boundary; this provider does not create ambient capabilities.
