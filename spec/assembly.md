# S3 Assembly textual 0.2

Status: normativo para o bootstrap.

## Formato

```asm
.function sum_to -> tryte
    .param r0, tryte
    .register r1, tryte
    .register r2, trit
.label entry
    TCONST r1, 0
    TCMP   r2, r0, r1
    TBR3   r2, negative, neutral, positive
.label negative
    TRET   r1
.label neutral
    TRET   r1
.label positive
    TCALL  r3, sum_to, r1
    TRET   r3
.end
```

`.param` declara parâmetros em ordem posicional. `.register` declara os demais
registradores. Declarações precedem `.label` e instruções. Todo registrador é
local ao frame e possui tipo fixo.

Cada função possui `.label entry`. Assembly 0.1 sem labels é aceita pelo parser
como um único bloco `entry`. Identificadores e labels seguem
`[A-Za-z_][A-Za-z0-9_]*`.

## Instruções

| Instrução | Operandos | Regra |
|---|---|---|
| `TCONST` | `dest, decimal` | valor cabe em `dest` |
| `TMOV` | `dest, source` | tipos iguais |
| `TINV` | `dest, source` | tipos iguais |
| `TADD` | `dest, left, right` | tipos iguais; overflow é erro |
| `TMIN` | `dest, left, right` | mínimo tritwise |
| `TMAX` | `dest, left, right` | máximo tritwise |
| `TCMP` | `trit_dest, left, right` | fontes do mesmo tipo |
| `TCALL` | `dest, function, args...` | assinatura e retorno compatíveis |
| `TRET` | `source` | tipo da função |
| `TJMP` | `label` | salto incondicional |
| `TBR3` | `trit, neg, zero, pos` | três labels existentes e distintos |

`TRET`, `TJMP` e `TBR3` são terminadores. Não existe `TSUB`.

## Metadados

Uma instrução pode terminar com:

```asm
; source=linha:coluna:offset
```

O renderer e parser preservam esse metadado. Outros comentários após `;` são
ignorados. Erros de execução incluem função, bloco, opcode, linha de assembly e
origem S3 quando disponíveis.

## Validação

Antes de executar, o emulador valida todas as funções, inclusive blocos
inalcançáveis: declarações, tipos, labels, terminadores e assinaturas. Leitura
de registrador não inicializado e overflow permanecem verificações dinâmicas.
Cada função deve conter ao menos um `TRET`; ciclos compostos apenas por saltos
são rejeitados neste bootstrap conservador.
