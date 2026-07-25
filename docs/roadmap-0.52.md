# Roadmap S3 0.52 — Match Fallback Arm (`else`)

## Visão Geral
Support for optional explicit fallback arms (`else:`) in `match` statements and `match` expressions.

## Sintaxe
```s3
# Match statement with fallback
match sel:
    0:
        return 5
    else:
        return 1

# Match expression with fallback
let val: tryte = match sel:
    1: 100
    else: 200
```

## Regras Semânticas e Validação
1. No máximo 1 arm de fallback (`else`).
2. O arm de fallback deve ser obrigatoriamente o último arm.
3. Nenhum arm de caso explícito pode aparecer após o arm de fallback.
4. O arm de fallback provê exaustividade completa para os casos faltantes em `{-1, 0, 1}`.
5. Se todos os três casos `{-1, 0, 1}` já estiverem presentes, a inclusão de um arm `else` é rejeitada como redundante (`redundant fallback arm`).

## Compilação e Lowering
- O lowering de IR reutiliza o opcode `BRANCH3` de 3 vias.
- Roteia os rótulos de casos ausentes para o bloco correspondente ao arm `else`.
- Preserva verificações de exaustividade, corretude estrutural e sintonização de registradores sem introduzir opcodes novos.
