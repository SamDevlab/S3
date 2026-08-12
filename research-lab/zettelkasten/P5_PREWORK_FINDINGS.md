# P5-PREWORK findings

## S3-ZK-0035 — Dynamic frequency changes the value of metadata evidence

TYPE=PERMANENT
STATUS=SUPPORTED_FOR_JSMN_AND_FOCUSED_CORPORA

Static origin is not runtime importance. The exact JSMN corpus has 5426
initialization-state accesses, but the instrumented native execution produced
21221 weighted initialization events, dominated by 14367 allocated-memory reset
events. Dynamic counters must remain separate from absolute timing.

## S3-ZK-0036 — Proven initialization checks are a bounded elision population

TYPE=BRIDGE
STATUS=SUPPORTED_FOR_EXACT_JSMN_CORPUS

The initialization analysis proves 228 TLOAD outcomes and 96 immutable-store
outcomes on the exact JSMN O1 candidate. These 324 checks are strong elision
candidates. This does not prove that register metadata stores or memory reset
stores are removable; observer and failure contracts still gate them.

## S3-ZK-0037 — Phi relevance is conditional on materialization

TYPE=PERMANENT
STATUS=SUPPORTED_AS_REFINED_MODEL

The JSMN pipeline has 712 internal O1 phis and 4135 phi edge operands before
out-of-SSA, even though its emitted Assembly IR exposes no phi nodes. A
phi-heavy source corpus produced 33 O1 phis. SSA is therefore relevant where
phi state reaches out-of-SSA/materialization, but the lexical residual cannot
be attributed to SSA alone.

## S3-ZK-0038 — TADDR blocks complete hosted differential closure

TYPE=NEGATIVE_RESULT
STATUS=SUPPORTED_FOR_CURRENT_EMULATOR

The native reference and slice workloads pass, while the hosted emulator
rejects `TADDR` as unsupported. The limitation must remain visible; it cannot
be converted into a false differential pass or a skip that erases the gap.
