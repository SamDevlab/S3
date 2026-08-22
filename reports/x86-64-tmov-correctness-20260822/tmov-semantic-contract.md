# TMOV Semantic Contract

`TMOV destination, source` is a value copy. The destination receives the
source value version observable at the moment the instruction executes.

After the move, a later write to `source` must not change the logical value
already assigned to `destination`. Lowering may use a physical residence or a
coalesced location only when that value-version equivalence is proven for every
later use. The repaired emitter therefore materializes the destination for
every non-self TMOV. `TMOV rX, rX` retains its initialization check and its
instruction accounting.
