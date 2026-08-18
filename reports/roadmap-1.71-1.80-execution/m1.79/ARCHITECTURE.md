# M1.79 - Content-Addressed Package Registry Client V1 Architecture

## MILESTONE

`M1.79 CONTENT_ADDRESSED_PACKAGE_REGISTRY_CLIENT_V1`

## PROBLEM

Package resolution needs immutable content identity and safe offline
installation without introducing publication or network trust assumptions.

## PUBLIC_SURFACE

`RegistryClient` reads a local index, resolves an exact name/version/hash
lock, verifies an object by SHA-256, uses an offline cache, and extracts a
validated archive. `RegistryLock` is the stable content identity record.

## OWNERSHIP_MODEL

Registry bytes are immutable values. Extraction writes only regular files under
the caller-owned destination. No package receives a raw filesystem pointer or
mutable registry handle.

## RESOURCE_MODEL

Index entries and archive members are bounded by configured limits. The client
is read-only; publication is an explicit unsupported operation.

## FAILURE_MODEL

Missing entry/object, malformed index, hash mismatch, duplicate identity,
offline cache miss, archive traversal, absolute path, link, and special file
are explicit `RegistryError` values. Validation happens before extraction.

## LOWERING_MODEL

Registry resolution is a hosted package-management service consumed by the
existing package lock model. It does not change compiler lowering or permit
remote code execution.

## DETERMINISM_MODEL

Entries are sorted by `(name, version, sha256)`, hashes are canonical lowercase
hex, and archive member validation/extraction order is lexical.

## PLATFORM_MODEL

The V1 client is offline/local-path based and platform-neutral. No public
registry or internet endpoint is required for correctness tests.

## OUT_OF_SCOPE

Publishing, authentication, signatures, mutable tags, dependency solving
beyond exact version/hash locks, and remote release automation.

## TEST_STRATEGY

Focused local-fixture tests cover deterministic resolution, cache hits,
checksum mismatch, missing objects, exact lock identity, traversal/absolute
path/link rejection, and publication refusal.
