# Milestone 1.36 - Host Services

This milestone defines an explicit dependency-injected host-service boundary.
Services have closed IDs, typed dynamic scalar arguments, and typed dynamic
scalar results. A registry is local to the embedding runtime; there is no
implicit global service, hidden host access, or automatic libc/filesystem
integration.

The initial IDs are `clock_monotonic` and `diagnostic`. Actual platform
implementations remain adapters supplied by the embedding environment.
