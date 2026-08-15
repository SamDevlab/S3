# S3-EXP-0029 - P8.2 preserved possibilities and collapse points

STATUS=COMPLETE_NO_VALID_TARGET_YET

The P8.2 question was whether a useful realization possibility is discarded
at a compiler boundary before the eventual consumer is known. The audit used
the P8.1 observer and failure witnesses as priors and ran a small deterministic
adjacent-opcode triage over the exact P7 production anchor. The triage is a
candidate finder only; it is not a semantic or dynamic proof.

The strongest established collapse is the conditional `TCMP -> TBR3` case,
but it is already P7 and is excluded from P8.2. The strongest unresolved
collapse is initialization and memory-state materialization. Its native checks
are observed by failure paths, memory-validity semantics, calls, aliases,
instruction limits, and successor consumers. P8.1 did not prove a
path-complete removable population.

The possibility-set notation is useful as a ledger for naming location,
representation, and proof loss. It is not yet justified as a compiler data
structure. Local producer/consumer rules explain the shipped P5-P7 wins with
less machinery and currently provide the stronger implementation challenger.

Result: no new P8 production target was promoted. No compiler code, production
branch, PR, merge, full candidate suite, or benchmark was created for P8.2.
