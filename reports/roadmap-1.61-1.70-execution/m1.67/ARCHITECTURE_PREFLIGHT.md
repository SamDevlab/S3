# M1.67 Architecture Preflight

## Existing authority

M1.48 provides numeric `NetworkAddress`, capability-scoped TCP handles,
bounded read/write limits, explicit close, fake hosted execution, and loopback
execution. DNS names are intentionally rejected by that TCP address type.

## Selected implementation

Keep TCP unchanged and add `UdpSocket` plus `DnsResolver` in a separate module.
UDP uses the existing normalized numeric address, bounded datagrams, blocking
timeouts, and explicit owned close. DNS delegates lookup to the host provider,
then canonicalizes results into sorted, duplicate-free `NetworkAddress` values.

## Boundary

No async or retry semantics are introduced. Network answers can vary by host,
but their in-memory representation is deterministic and local loopback tests
do not depend on public internet access.
