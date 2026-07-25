# S3 Milestone 0.47 — Static Array Len Expression

**Status**: completed

## Objetivos

Adicionar a expressão estática `len(array_expression)` na sintaxe fonte S3 0.6 para obter o comprimento de um array estático sem custo em tempo de execução.

## Motivação

Permitir iteração genérica e segura sobre arrays usando a construção `for i: tryte in range(0, len(values)):`, eliminando a necessidade de repetir constantes literais no limite do range e reduzindo o risco de erros de acoplamento de limites.

## Candidatos Avaliados

1. **Candidato A: Tamanho Estático de Array (`len(values)`)** — ESCOLHIDO. Avaliação 100% estática em compilação, 0 opcodes de IR, 0 overhead de memória ou chamada.
2. **Candidato B: Atribuição Composta (`+=`, `-=`)** — Rejeitado. Mero açúcar sintático.
3. **Candidato C: Range com Limite Único (`range(end)`)** — Rejeitado. Sobrecarga sintática adicional sem ganho estático.
4. **Candidato D: Range com Passo (`range(start, end, step)`)** — Rejeitado. Introduz complexidade adicional de análise de sinal e direção.
5. **Candidato E: Loop Infinito Explícito (`loop:`)** — Rejeitado. Redundante frente a `while -1:`.

## Matriz de Decisão

| Candidato | Ganho Prático | Custo de Runtime | Novas Palavras-chave | Opcodes Novos | Escolhido? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Tamanho de Array (`len`)** | **Alto** | **0** | `len` (V0.6) | **0** | **SIM** |
| B. Atribuição Composta | Baixo | 0 | 0 | 0 | Não |
| C. Range Limite Único | Baixo | 0 | 0 | 0 | Não |
| D. Range com Passo | Médio | Baixo | 0 | 0 | Não |
| E. Loop Infinito | Baixo | 0 | 0 | 0 | Não |

## Sintaxe

```s3
fn sum_elements(values: tryte[5]) -> tryte:
    mut total: tryte = 0
    for i: tryte in range(0, len(values)):
        total = total + values[i]
    return total
```

## Semântica

- `len(array_expression)` aceita exatamente uma expressão cujo tipo resolvido seja um `ast.ArrayType` (`tryte[N]` ou `trit[N]`).
- O operando é validado durante a análise semântica. Se o operando não for um array estático (ex.: escalar `tryte`, elemento `values[i]` ou literal inteiro `5`), um erro semântico determinístico é emitido.
- O resultado é um escalar do tipo `tryte` com o valor numérico `N`.
- A avaliação ocorre exclusivamente em tempo de compilação. Nenhum `LOAD`, `STORE`, `CALL` ou opcode novo de IR é gerado.

## Regras de Tipos e Avaliação

- Operando: `ast.ArrayType(element_type, length)`.
- Resultado: `ast.TypeName.TRYTE`.
- Ordem de avaliação: puramente estática em tempo de compilação.

## Escopo

- Nó AST `LenExpression(argument, location)`.
- Token `LEN` no lexer e tokenização do identificador `len` como `TokenKind.LEN` no modo V0.6.
- Parsing em `_parse_primary` e `_parse_len_v0_6`.
- Validação semântica em `_analyze_len`, armazenando o tipo do array e retornando `TRYTE`.
- Lowering em `_lower_len` emitindo diretamente uma constante `tryte` imediata `N`.
- Suporte em `static_strings.py` para travessia do operando de `LenExpression`.
- Suíte completa de testes de parser, semântica, lowering e execução.
- Atualização de especificações (`spec/grammar.ebnf`, `spec/source-syntax-0.6.md`, `spec/language.md`) e `README.md`.

## Não Escopo

- Avaliação de `len` em tempo de execução.
- Arrays dinâmicos ou fatias (slices).
- Retorno de arrays por funções ou passagem dinâmica.
- Modificação de opcodes IR ou formatos de montagem.

## Testes

- `tests/test_s3_array_len_parser.py`: Cobertura de parsing em declarações, laços `for`, retornos e tratamento de erros de sintaxe.
- `tests/test_s3_array_len_semantic.py`: Validação de operandos `tryte[...]` e `trit[...]` e rejeição de escalares, elementos indexados e identificadores não declarados.
- `tests/test_s3_array_len_lowering.py`: Validação de IR e verificação do `verify_ir`.
- `tests/test_s3_array_len_execution.py`: Testes de execução no emulador cobrindo somatórias em laço `for`, expressões aritméticas com `len`, `match` com `len` e paridade de runtime.

## Critérios de Aceitação

- [x] Parsing da palavra-chave `len(...)` no modo V0.6.
- [x] Preservação de `len` como identificador normal no modo V0.5.
- [x] Validação semântica estrita de tipos de operandos.
- [x] Lowering direto para constante `tryte` sem opcodes novos nem custo em runtime.
- [x] Integração completa com laços `for i: tryte in range(0, len(arr)):`.
- [x] Testes de parser, semântica, lowering e execução aprovados.
- [x] Especificações e documentação atualizadas.

## Checklist

- [x] AST, Lexer e Parser implementados.
- [x] Análise semântica implementada.
- [x] Lowering e travessia de strings estáticas implementados.
- [x] Testes criados e aprovados.
- [x] Documentação e especificações atualizadas.
