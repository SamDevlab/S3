# Milestone 1.43 - Scoped Host Resources and Capability Enforcement

Status: COMPLETE.

## Goal

Give resource-using programs an explicit capability and handle boundary with
deterministic lifetime, cleanup, and failure behavior.

## Delivered contract

- closed source types host_capability and resource_handle;
- explicit grant, open, inspect, invoke, and mutable close builtins;
- registry-scoped opaque Python capabilities and handles;
- provider registration through ResourceProvider;
- reverse-order ResourceScope cleanup;
- deterministic slot limits and generation reuse;
- use-after-close and double-close rejection;
- bounded source/IR and Linux x86-64 native fixture equivalence;
- 8-byte i64 memory support for opaque handle cells.

The native path is deliberately a deterministic provider fixture. It does not
open host files, spawn processes, or create sockets. Real OS providers remain
an embedding concern and must be registered explicitly.

## Verification gates

- focused M1.43 and host-service tests: PASS (9 tests);
- hosted source lifecycle O0/O1: PASS (2, 2);
- Linux x86-64 SSH native lifecycle O0/O1: PASS (2, 2);
- Assembly verification and native generation: PASS;
- compileall: PASS;
- diff check: PASS;
- full suite: terminal exit 0;
- no generic resource syntax, exceptions, ambient host access, benchmark,
  remote write, Docker, virtualization, or shutdown action.

## Boundary

M1.43 is closed. M1.44 is the next milestone and owns the small layered
standard-library core. M1.43 does not reopen the M1.42 result representation
and does not claim real POSIX provider coverage.
