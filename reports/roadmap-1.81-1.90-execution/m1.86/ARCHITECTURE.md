# M1.86 Architecture

M1.86 adds a read-only remote registry transport contract for HTTPS/TLS and
content-addressed objects. A registry object is requested by a lowercase
SHA-256 digest, the URI must use HTTPS, and the injected transport must report
certificate/hostname verification as successful. The client verifies the
returned bytes independently before exposing or caching them.

The cache is bounded by entry count and total bytes. Entries are immutable,
verified before insertion, and evicted deterministically in insertion order.
There is no remote publish path, no HTTP fallback, no unverified cache hit, no
credential handling, and no external network use in the tests; the fixture
transport models only the verified HTTPS boundary.
