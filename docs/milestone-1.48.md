# Milestone 1.48 - Capability-Scoped Network Provider

Status: IMPLEMENTATION_COMPLETE_WITH_DEFERRED_ENVIRONMENT_CERTIFICATION.

## Delivered contract

- numeric IPv4/IPv6 addresses with deterministic 19-byte normalization;
- separate client and listener capabilities;
- opaque listener/stream handles owned by a bounded registry;
- blocking millisecond timeouts with explicit timeout and EOF results;
- bounded, possibly partial byte reads and writes;
- idempotent close and deterministic use-after-close errors;
- bounded canonical operation/error traces;
- deterministic hosted fake provider;
- real blocking TCP loopback provider using the host socket API.

DNS, UDP, TLS, async syntax, threads, and unrestricted remote networking are
outside this milestone.

## Verification

- focused M1.48 network tests plus M1.43 resource, host-service, and M1.47
  buffer regression tests: PASS (25);
- fake round-trip, partial I/O, timeout, EOF, capability denial, resource
  limits, close, deterministic trace, and local loopback: PASS;
- fake/loopback normalized operation and status traces: PASS;
- compileall: PASS;
- diff check: PASS;
- full suite on exact candidate
  `13a3e3bbfe173d41a07463634dcb4af2334d1a9d`: terminal exit 0;
- Linux x86-64 loopback certification: DEFERRED; no source was copied to the
  remote VM and no unsupported native claim is made.

No benchmark, remote write, CI trigger, Docker/virtualization change, or
shutdown action was performed.

## Boundary

The hosted capability and provider contract is closed. Linux-specific socket
certification remains an environment gate; M1.49 may consume the capability
mapping without expanding the network surface.
