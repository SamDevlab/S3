# Milestone 1.67 - UDP and DNS Resolver V1

## Architecture status

M1.67 adds a separate blocking `UdpSocket` and `DnsResolver` surface in
`bootstrap.s3.udp_dns`. UDP handles are owned values with explicit,
idempotent close; datagrams are bounded by a configured maximum; and send,
receive, bind, and close failures are typed `Result` values. Timeout is a
terminal outcome for one operation, with no hidden retry loop.

DNS uses the system resolver, but its result representation is deterministic:
numeric addresses are normalized to the existing `NetworkAddress`,
deduplicated by serialized address, and sorted by family, host, and port.
Resolver answers remain external inputs and are never treated as compiler
nondeterminism.

## Compatibility and safety

The existing TCP `NetworkRegistry`, fake provider, loopback provider, numeric
address format, limits, and traces are unchanged. No async scheduler, raw
socket handle in the language surface, public-internet fixture, or unbounded
buffer was added.
