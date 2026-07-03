# S3 IR 0.2

Status: normativo.

## Modelo

Um `IRModule` contém funções. Cada função contém:

- nome e tipo de retorno;
- parâmetros ligados a registradores tipados;
- tabela de registradores/valores virtuais;
- blocos básicos nomeados;
- localização de origem opcional.

`entry` é o bloco de entrada obrigatório. Registradores têm tipo imutável e uma
única definição; parâmetros contam como definições. A visão achatada
`function.instructions` existe apenas para inspeção/compatibilidade, não define
controle de fluxo.

## Instruções

| Opcode | Forma | Semântica |
|---|---|---|
| `CONST` | `dest, immediate` | constante verificada |
| `MOVE` | `dest, source` | cópia do mesmo tipo |
| `INVERT` | `dest, source` | inversão ternária |
| `ADD` | `dest, left, right` | soma verificada |
| `MINIMUM` | `dest, left, right` | mínimo tritwise |
| `MAXIMUM` | `dest, left, right` | máximo tritwise |
| `COMPARE` | `trit_dest, left, right` | comparação ternária |
| `CALL` | `dest, function, args...` | chamada tipada |

Terminadores:

| Opcode | Forma |
|---|---|
| `RETURN` | `source` |
| `JUMP` | `target` |
| `BRANCH3` | `trit_condition, negative, neutral, positive` |

Cada bloco termina exatamente uma vez e não possui instruções posteriores.
Destinos de `BRANCH3` são distintos e correspondem, nessa ordem, a `-1`, `0` e
`1`.

Não existe `SUBTRACT`. `a - b` emite `INVERT(b)` e `ADD(a, inverted)`.

## Verificador

`verifier.py` é independente do lowering e rejeita:

- função sem `entry`;
- função/bloco/valor duplicado;
- bloco sem terminador ou instrução após terminador;
- destino inexistente ou destinos ternários duplicados;
- `BRANCH3` não controlado por `trit`;
- valor inexistente ou não definido;
- operação com tipos incompatíveis;
- chamada inexistente, aridade/tipos incorretos ou destino de retorno errado;
- retorno incompatível;
- opcode desconhecido ou de subtração.

O codegen sempre chama o verificador antes de produzir assembly.

## Origem

Registradores, parâmetros, blocos e instruções podem carregar
`SourceLocation(offset, line, column)`. Comparações, chamadas, saltos ternários
e retornos gerados pelo frontend preservam esses metadados.

Não existem `PHI`: variáveis são imutáveis e nomes declarados em casos não
escapam do ramo.

