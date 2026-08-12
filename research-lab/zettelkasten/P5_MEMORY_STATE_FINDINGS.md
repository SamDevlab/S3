# P5 Audit Findings

## S3-ZK-0032 - The byte-frame metadata metric is physically broader than metadata

TYPE=PERMANENT
STATUS=SUPPORTED

The P4 lexical count `byte ptr [rbp]` contains register initialization bytes,
memory initialization bytes and byte-sized trit payload data. A semantic audit
must decompose storage regions before calling the result metadata.

## S3-ZK-0033 - SSA is not dominant in the P4 JSMN residual

TYPE=NEGATIVE_RESULT
STATUS=SUPPORTED_FOR_CORPUS

The JSMN P4 candidate has loops but no phi nodes, phi edge copies or critical
edges after O1 lowering. The unchanged byte-frame count is therefore not
evidence that SSA destruction dominates this workload.

## S3-ZK-0034 - Initialization state and residence form interacting dimensions

TYPE=BRIDGE
STATUS=SUPPORTED_AS_RESEARCH_MODEL

The emitter tracks initialized state in bytes while physical register
residence can leave the canonical frame value stale until a snapshot observer.
A reduced product of initialization, residence and observability is a useful
research model, but no production domain has been implemented.
