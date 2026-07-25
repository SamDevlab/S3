# S3 Milestone 0.46 — For-in-range Loop Statement

**Status**: completed

## Objetivos

Adicionar a construção de laço `for` com intervalo estático (`for var: tryte in range(start, end):`) na sintaxe fonte S3 0.6.

## Motivação

Fornecer iteração determinística sobre intervalos de `tryte` sem a necessidade de gerenciamento manual de variáveis mutáveis de contador de laço e blocos `while` repetitivos.

## Contrato

- **Sintaxe**: `for var: tryte in range(start_expr, end_expr):` seguido por um bloco indentado.
- **Variável de Laço**: Declarada com o tipo `tryte`, imutável no corpo do laço, com escopo restrito ao bloco do laço.
- **Limites de Intervalo**: Ambas as expressões `start_expr` e `end_expr` devem ser do tipo `tryte`.
- **Intervalo**: Meio-aberto `[start, end)`. Se `start >= end`, o corpo é executado zero vezes.
- **Desvios de Laço**: `break` e `continue` operam no laço `for` mais interno. `break` salta para a saída do laço e `continue` salta para o passo de incremento do laço.
- **Lowering**: Baixado utilizando `COMPARE`, `BRANCH3`, slot de memória local (`IRMemoryObject`), `ADD` e `JUMP`. Zero novos opcodes de IR.

## Sintaxe

```s3
fn sum_range(n: tryte) -> tryte:
    mut total: tryte = 0
    for i: tryte in range(0, n):
        total = total + i
    return total
```

## Semântica

1. `start_expr` e `end_expr` são avaliadas.
2. A variável de laço é alocada na memória local do frame e inicializada com `start_val`.
3. No bloco de condição (`for_cond`), a comparação `COMPARE(cur_val, end_val)` produz `-1` se `cur_val < end_val` (executa corpo), `0` se igual (sai do laço), ou `1` se maior (sai do laço).
4. No bloco de incremento (`for_step`), a variável de laço é incrementada por 1 via `ADD` e armazenada de volta na memória.

## Regras de Tipos

- `start_expr` e `end_expr`: exigem tipo `ast.TypeName.TRYTE`.
- `variable_type`: exige tipo `ast.TypeName.TRYTE`.
- A variável de laço é imutável (`is_mutable=False`).

## Escopo

- Definição do nó AST `ForStatement`.
- Tokens `FOR`, `IN`, `RANGE` e parsing de `for` em `parser.py` para modo V0.6.
- Análise semântica em `semantic.py` validando tipos dos limites, declarando a variável no escopo filho e garantindo imutabilidade.
- Lowering em `lowering.py` com desvios `BRANCH3`, incremento e integração de `break`/`continue` no `loop_stack`.
- Suporte em `static_strings.py` para travessia de expressões em `ForStatement`.
- Suíte completa de testes de parser, semântica, lowering e execução.
- Especificação (`spec/grammar.ebnf`, `spec/source-syntax-0.6.md`, `spec/language.md`) e `README.md` atualizados.

## Não Escopo

- Novos opcodes de IR.
- Passos de incremento customizados (step != 1).
- Iteração sobre arrays ou coleções dinâmicas.
- Alterações nos formatos de arquivo IR JSON ou S3 Assembly.

## Arquitetura e Lowering

- **AST**: `ForStatement` contém nome da variável, tipo, expressão inicial, expressão final, bloco e localização.
- **Parser**: `_parse_for_v0_6` consome a estrutura da instrução `for var: tryte in range(start, end):`.
- **Semântica**: `_analyze_for` verifica os tipos e introduz o binding no escopo local ao bloco.
- **Lowering**: `_lower_for` aloca memória local para o contador de laço, avalia a condição via `COMPARE` + `BRANCH3`, aloca o bloco `for_step` para o incremento e conecta o `loop_stack` para suporte a `break` e `continue`.

## Testes

- `tests/test_s3_for_parser.py`: Cobertura de parsing de `for`, blocos internos e rejeição de erros de sintaxe.
- `tests/test_s3_for_semantic.py`: Validação de tipos dos limites e verificação de imutabilidade da variável de laço.
- `tests/test_s3_for_lowering.py`: Validação de IR e aprovação no `verify_ir`.
- `tests/test_s3_for_execution.py`: Testes de execução no emulador cobrindo somatórias, limites com deslocamento, intervalos vazios, `break`, `continue` e laços `for` aninhados.

## Critérios de Aceitação

- [x] Parsing de `for` no modo V0.6.
- [x] Validação semântica dos limites `tryte` e imutabilidade da variável de laço.
- [x] Lowering correto em IR SSA usando opcodes existentes.
- [x] Suporte total a `break` e `continue`.
- [x] Execução no emulador e backend nativo.
- [x] Documentação e especificações atualizadas.

## Limitações

- Suporta exclusivamente passo unitário (`+1`) sobre intervalos de `tryte`.

## Checklist

- [x] AST, Lexer e Parser implementados.
- [x] Análise semântica implementada.
- [x] Lowering e travessia de strings estáticas implementados.
- [x] Testes de parser, semântica, lowering e execução criados e aprovados.
- [x] Documentação e especificações atualizadas.
