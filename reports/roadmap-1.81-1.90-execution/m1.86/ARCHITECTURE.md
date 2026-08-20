# M1.86 Architecture

M1.86 is a read-only content-addressed registry client layered on the real bounded M1.85 HTTP client. Registry origin is an explicit canonical HTTPS authority and becomes part of each object's immutable identity. Publishing remains disabled.

The authority boundary accepts ASCII DNS-style host names, lowercases them before any identity or transport use, and rejects empty labels, leading/trailing label hyphens, trailing-dot aliases, and non-ASCII V1 origins. As a result, case variants cannot create distinct immutable registry identities for the same DNS host.

An object request is `https://<authority>/objects/<lowercase-sha256>`. `HTTPSContentAddressedRegistry` delegates transport to `BoundedHTTPClient`, whose default HTTPS path uses certificate-required, hostname-checked TLS. The registry requires HTTP 200, independently hashes returned bytes, and exposes/caches them only after the digest matches. 404 and other statuses are explicit failures.

The verified cache is bounded by entry count and total bytes and evicts deterministically. Cache hits contain only previously hash-verified bytes. There is no HTTP downgrade, provider-supplied `certificate_verified` boolean, credential handling, or publish path. Tests use an injected HTTPS transport boundary without public network access while asserting that registry requests remain HTTPS, canonical origin identity is stable, and content verification stays independent of transport.
