# S3 Milestone 0.45 — Match Expression

**Status**: completed

## Objetivos

Adicionar suporte ao `match` no nível de expressão (`MatchExpression`) na sintaxe fonte S3 0.6.

## Motivação

Permitir a seleção inline de valores com base em um seletor `trit` diretamente dentro de expressões (inicializadores de variáveis, retornos, argumentos de funções), eliminando a necessidade de declarar variáveis mutáveis auxiliares e blocos `match` como statement para simples atribuições condicionais.

## Contrato

- **Sintaxe**: `match selector:` seguido por bloco indentado contendo três braços (`-1`, `0`, `1`), cada um com uma expressão de resultado.
- **Seletor**: Deve ser uma expressão do tipo `trit`.
- **Exaustividade**: Exige exatamente os três casos `-1`, `0` e `1`.
- **Expressões de Braço**: Cada braço produz uma única expressão. Todos os braços devem produzir o mesmo tipo escalar (`trit` ou `tryte`).
- **Avaliação Preguiçosa**: Apenas o braço selecionado pelo seletor é avaliado em tempo de execução. Expressões de braços não selecionados não são executadas.
- **Lowering**: Baixado utilizando `BRANCH3`, alocação de memória local temporária (`IRMemoryObject`), `STORE` em cada braço e `LOAD` no bloco de continuação. Zero novos opcodes de IR.

## Sintaxe

```s3
fn abs_val(x: tryte) -> tryte:
    return match x <=> 0:
        -1: ~x + 1
        0: 0
        1: x
```

## Semântica

1. O seletor é avaliado exatamente uma vez e deve produzir um `trit`.
2. A análise estática valida a corretude dos três braços (`-1`, `0`, `1`) e exige o mesmo tipo de retorno para todos.
3. Em execução, `BRANCH3` desvia para o bloco do braço correspondente ao valor do seletor.
4. O valor resultante é armazenado em slot temporário de frame local e carregado no bloco de continuação.

## Comportamento Ternário e Regras de Tipos

- O seletor aceita estritamente `trit` (-1, 0, 1).
- Todos os braços devem convergir para o mesmo tipo escalar (`trit` ou `tryte`).
- Não há coerção implícita ou truthiness.

## Escopo

- Definição dos nós AST `MatchExpression` e `MatchExpressionCase`.
- Parsing de `match` como expressão no modo V0.6 em `_parse_primary`.
- Validação semântica em `semantic.py` garantindo seletor `trit`, exaustividade dos 3 braços e consistência dos tipos de resultado.
- Lowering em `lowering.py` com convergência via memória local temporária.
- Suporte em `static_strings.py` para travessia de strings estáticas em sub-expressões.
- Suíte completa de testes de parser, semântica, lowering, execução e avaliação preguiçosa.
- Especificação (`spec/grammar.ebnf`, `spec/source-syntax-0.6.md`, `spec/language.md`) e `README.md` atualizados.

## Não Escopo

- Novos opcodes de IR.
- Coerção ou conversão implícita de tipos entre braços.
- Retorno de arrays a partir de braços de `match`.
- Alterações nos formatos de arquivo IR JSON ou S3 Assembly.

## Arquitetura e Lowering

- **AST**: `MatchExpression` contém seletor e tupla de `MatchExpressionCase`.
- **Parser**: Desambiguação natural entre statement e expression pelo contexto de parsing (`_parse_primary` vs `_parse_statement`).
- **Semântica**: `_analyze_match_expression` verifica estaticamente a completude e consistência de tipos.
- **Lowering**: `_lower_match_expression` gera `BRANCH3` para três blocos de braço. Cada bloco escreve o resultado via `STORE` no slot de memória temporária e salta para `match_expr_cont`, onde o valor é lido via `LOAD`. Mantenha 100% das invariantes SSA e regras do IR verifier.

## Testes

- `tests/test_s3_match_expression_parser.py`: Cobertura de parsing em inicializadores, retornos, chamadas e aninhamentos.
- `tests/test_s3_match_expression_semantic.py`: Validação de tipos do seletor, braços incompatíveis e não-exaustivos.
- `tests/test_s3_match_expression_lowering.py`: Validação de lowering para IR e aprovação no `verify_ir`.
- `tests/test_s3_match_expression_execution.py`: Testes de execução no emulador e verificação de avaliação preguiçosa (garantindo que braços não selecionados com chamadas recursivas infinitas não são executados).

## Critérios de Aceitação

- [x] Parsing de `match` como expressão na sintaxe V0.6.
- [x] Validação semântica de seletor `trit` e exaustividade dos braços.
- [x] Lowering correto em IR SSA usando memória temporária e `BRANCH3`.
- [x] Avaliação preguiçosa provada por testes de execução.
- [x] Execução no emulador e paridade nativa.
- [x] Documentação e especificações atualizadas.

## Limitações

- `MatchExpression` aceita apenas braços que contêm uma única expressão de retorno por caso (não aceita blocos arbitrários de statements dentro dos braços de expressão).

## Checklist

- [x] AST e Parser implementados.
- [x] Análise semântica implementada.
- [x] Lowering e travessia de strings implementados.
- [x] Testes de parser, semântica, lowering, execução e avaliação preguiçosa criados e aprovados.
- [x] Documentação e especificações atualizadas.
