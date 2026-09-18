# Verifier Invariant Matrix

| Invariant | Reference behavior | Generic representation | Positive | Negative | Hosted | Native | Differential |
| --- | --- | --- | --- | --- | --- | --- | --- |
| function identity | unique function names | function symbol ID + direct FunctionId | scalar program | duplicate symbol | PASS | pending | PASS |
| static order | deterministic static strings | StaticStringArena direct IDs | ordered entries | out-of-order IDs | PASS | pending | PASS |
| value definition | one producer | ValueArena + definition registry | const/return | duplicate producer | PASS | pending | PASS |
| operand validity | every use exists | operand ID range | scalar program | unknown operand | PASS | pending | PASS |
| memory validity | bounded typed storage | MemoryObjectArena | load/store | bad length/type | PASS | pending | PASS |
| block shape | one final terminator | BlockId + instruction range | jump/return | missing/multiple/late | PASS | pending | PASS |
| call signature | exact params/results | FunctionId/capability authority | two-cell call | width mismatch | PASS | pending | PASS |
| references | metadata matches target | typed reference fields | reference shape | malformed metadata | PASS | pending | PASS |
| multi-result | width is explicit | result ID ranges | 0/1/N calls | collapsed width | PASS | pending | PASS |
| CFG | targets are blocks | target BlockId ranges | branch/join | unknown target | PASS | pending | PASS |
| reachability | entry-directed traversal | external verifier state | branch graph | invalid entry | PASS | pending | PASS |
| dominance | definitions dominate uses | deterministic dominator sets | join graph | use before definition | PASS | pending | PASS |
| immutability | verifier is observational | digest before/after | repeated verify | mutation detection | PASS | pending | PASS |

The Linux x86-64 focused shape qualification passed through the project
NativeToolchain for all three S3 shape fixtures, with the expected hosted
program result and empty stderr. The verifier invariant rows remain hosted
evidence: the VM has no pytest installation, and the native probe does not
claim to execute Python verifier objects natively.
