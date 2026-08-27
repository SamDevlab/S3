# Stage 10 — General Emitter qualification and closure

## Goal

Use the now-qualified semantic IR to close the actual General Emitter capability gap.

## Entry gate

Canonical semantic integration must already be proven, unless a later control revision explicitly authorizes emitter work against the candidate source only.

## Required principles

- consume semantic records/structures, not lexical shortcuts;
- do not add self-source-specific special cases;
- preserve ABI/signature semantics;
- support literals, parameters, locals, expression results, calls, arrays/indexing, loops, match/BRANCH3 and required control flow from the canonical source;
- emitter failure for unsupported semantic opcode remains fail-closed.

## Qualification

Run focused codegen/native fixtures first, then the canonical Stage1 source.

Record exact source/candidate/emitted artifact SHAs and observable results.

## Exit gate

```text
S1=PASS
S2=PASS
S3=PASS
S4=PASS
S5=PASS
GENERAL_EMITTER=PASS
CANONICAL_STAGE1_EMISSION=PASS
```

Do not attempt SELF_EMIT unless the live control manifest separately authorizes it.
