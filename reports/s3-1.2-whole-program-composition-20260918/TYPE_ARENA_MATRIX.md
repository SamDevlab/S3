# TypeArena Matrix

| Family | Identity rule | Layout authority | Evidence |
|---|---|---|---|
| trit, tryte, i64, f64, string, bytes, text | fixed reserved TypeId order | existing language authority | primitive ID test |
| vector/map/set | kind + element/type arguments | existing collection authority | structural key tests |
| array | kind + element TypeId + length | existing fixed-value layout | invalid size and canonical repeat tests |
| reference/slice | kind + element TypeId + mutability | existing reference/slice authority | structural identity test |
| record/enum | defining ModuleId + NominalTypeId | existing nominal layout authority | registry and nominal tests |
| type parameter | owner identity + ordinal | not a runtime layout | owner-sensitive key |
| instantiated nominal | generic nominal + ordered TypeIds | existing nominal layout authority | parametric key contract |

TypeArena interning is append-only with transactional rollback. Equivalent keys
share a TypeId, and rollback never renumbers an already committed identity.
