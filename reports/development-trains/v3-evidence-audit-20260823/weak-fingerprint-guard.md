# Weak fingerprint guard

`%181` identities and small folds remain available only as legacy telemetry.
The M2.81–M2.83 exact evidence path compares bounded structures and canonical
bytes/SHA-256. Contract tests reject using `identity` inside exact `match`
gates. This guard is required for M2.87/M2.88/M2.90/M3.00 evidence.

M278_IDENTITY_MOD181=BOUNDED_EXPERIMENTAL_EVIDENCE_ONLY
M278_IDENTITY_ACCEPTABLE_FOR_M300=NO
WEAK_FINGERPRINT_M3_GUARD=PASS
