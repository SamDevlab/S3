# Verifier Invariant Matrix

| Invariant | Reference behavior | Generic representation | Positive | Negative | Hosted | Native | Differential |
| --- | --- | --- | --- | --- | --- | --- | --- |
| function identity | unique function names | function symbol ID + direct FunctionId | scalar program | duplicate symbol | PASS | PASS | PASS |
| static order | deterministic static strings | StaticStringArena direct IDs | ordered entries | out-of-order IDs | PASS | PASS | PASS |
| value definition | one producer | ValueArena + definition registry | const/return | duplicate producer | PASS | PASS | PASS |
| operand validity | every use exists | operand ID range | scalar program | unknown operand | PASS | PASS | PASS |
| memory validity | bounded typed storage | MemoryObjectArena | load/store | bad length/type | PASS | PASS | PASS |
| block shape | one final terminator | BlockId + instruction range | jump/return | missing/multiple/late | PASS | PASS | PASS |
| call signature | exact params/results | FunctionId/capability authority | two-cell call | width mismatch | PASS | PASS | PASS |
| references | metadata matches target | typed reference fields | reference shape | malformed metadata | PASS | PASS | PASS |
| multi-result | width is explicit | result ID ranges | 0/1/N calls | collapsed width | PASS | PASS | PASS |
| CFG | targets are blocks | target BlockId ranges | branch/join | unknown target | PASS | PASS | PASS |
| reachability | entry-directed traversal | external verifier state | branch graph | invalid entry | PASS | PASS | PASS |
| dominance | definitions dominate uses | deterministic dominator sets | join graph | use before definition | PASS | PASS | PASS |
| immutability | verifier is observational | digest before/after | repeated verify | mutation detection | PASS | PASS | PASS |

The Linux x86-64 focused qualification now executes the S3 verifier itself in
native processes: 32 deterministic valid/invalid cases were compared against
the hosted result, with zero differential failures. Digest equality was part
of every encoded result, and six representative cases were repeated three
times in fresh native processes. The native program contains the IR-shaped
data and verifier logic; no Python callback or expected-result injection is
used. The full Linux suite at the same source head passed with one skip.
