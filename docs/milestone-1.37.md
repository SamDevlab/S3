# Milestone 1.37 - Project Container Model

This milestone defines a deterministic immutable project container made of a
named root and sorted, uniquely named project units. Each unit owns a sorted,
unique list of source names, and the complete manifest has a stable SHA-256
identity.

Filesystem discovery, compilation scheduling, package registries, and process
execution are outside this structural model and must be injected by later
adapters.
