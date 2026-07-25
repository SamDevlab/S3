# S3 Milestone 0.44 — Binary Relational Operators

**Status**: completed

## Objetivos

Adicionar suporte aos operadores relacionais binários `==` (igual), `!=` (diferente), `<` (menor), `<=` (menor ou igual), `>` (maior) e `>=` (maior ou igual) na sintaxe fonte S3 0.6.

## Motivação

Atualmente em S3, comparações de controle de fluxo contam apenas com o operador ternário de espaçonave `<=>`. A realização de testes diretos de igualdade (`==`), desigualdade (`!=`) ou faixas em laços `while` exige padronizações verbosas com `while -1:` combinados com `match` e `break`/`continue`. A introdução de operadores relacionais binários amplia a expressividade da linguagem de maneira direta sem necessitar de novas infraestruturas de IR ou opcodes nativos.

## Contrato

- **Sintaxe**: Operadores binários `==`, `!=`, `<`, `<=`, `>`, `>=` aceitos em expressões.
- **Operandos**: Ambos os operandos devem ter o mesmo tipo escalar (`tryte` com `tryte`, ou `trit` com `trit`).
- **Tipo de Retorno**: Sempre `trit`.
- **Valor Verdade**:
  - `-1`: Verdadeiro (True) — satisfaz e executa corpos de laços `while`.
  - `0`: Falso (False) — encerra laços `while`.
- **Lowering**: Mapeados para instruções IR existentes `COMPARE`, `BRANCH3`, `STORE` e `LOAD`. Zero novos opcodes de IR.

## Escopo

- Definição dos membros de enum em `ast.BinaryOperator`.
- Definição dos tokens `EQUAL_EQUAL`, `NOT_EQUAL`, `LESS`, `LESS_EQUAL`, `GREATER`, `GREATER_EQUAL` em `lexer.TokenKind`.
- Suporte a parsing em `parser.py` adicionando a regra de precedência `_parse_relational()`.
- Análise semântica em `semantic.py` garantindo operandos do mesmo tipo e tipo de resultado `trit`.
- Lowering em `lowering.py` utilizando o opcode `COMPARE` e derivando os valores verdade através de ramificação `BRANCH3` com armazenamento seguro em memória local para manutenção do modelo SSA.
- Suíte de testes dedicada para parser, análise semântica, lowering e execução no emulador.
- Atualização da especificação (`spec/grammar.ebnf`, `spec/source-syntax-0.6.md`, `spec/language.md`) e `README.md`.

## Não Escopo

- Novos opcodes de IR.
- Operadores de atribuição composta (`+=`, `-=`).
- Coerção ou conversão implícita de tipos.
- Truthiness implícita fora de `trit`.
- Alterações nos formatos IR JSON ou S3 Assembly.

## Sintaxe

```s3
fn main() -> tryte:
    mut i: tryte = 0
    while i != 5:
        i = i + 1
    return i
```

## Semântica

- `a == b`: Retorna `-1` se `a` for igual a `b`; caso contrário, retorna `0`.
- `a != b`: Retorna `-1` se `a` for diferente de `b`; caso contrário, retorna `0`.
- `a < b`: Retorna `-1` se `a` for estritamente menor que `b`; caso contrário, retorna `0`.
- `a <= b`: Retorna `-1` se `a` for menor ou igual a `b`; caso contrário, retorna `0`.
- `a > b`: Retorna `-1` se `a` for estritamente maior que `b`; caso contrário, retorna `0`.
- `a >= b`: Retorna `-1` se `a` for maior ou igual a `b`; caso contrário, retorna `0`.

## Arquitetura

- **Lexer**: `_operator_or_punctuation` reconhece os operadores binários de 2 caracteres (`==`, `!=`, `<=`, `>=`) antes dos de 1 caractere (`<`, `>`), mantendo a precedência do operador `<=>`.
- **AST**: Integrados em `BinaryOperator`.
- **Parser**: Adicionada a camada de precedência `_parse_relational()` entre o nível de comparação `<=>` e o nível principal de expressão.
- **Semântica**: `_analyze_binary` agrupa todos os operadores relacionais, garantindo tipos compatíveis nos operandos e estabelecendo `trit` como tipo final.
- **Lowering**: `_lower_relational_expression` executa `COMPARE`, aloca memória local temporária de 1 `trit`, gera ramificações `BRANCH3` para preencher o resultado (`-1` ou `0`) conforme o operador, e carrega o valor via `LOAD`.

## Testes

- `tests/test_s3_relational_parser.py`: Testes de parsing e precedência dos operadores relacionais.
- `tests/test_s3_relational_semantic.py`: Validação semântica de tipos e rejeição de operandos incompatíveis.
- `tests/test_s3_relational_lowering.py`: Validação de lowering para IR e verificação via `verify_ir`.
- `tests/test_s3_relational_execution.py`: Execução no emulador cobrindo todas as operações relacionais e laços `while`.

## Critérios de Aceitação

- [x] Tokens e parsing de `==`, `!=`, `<`, `<=`, `>`, `>=` na sintaxe V0.6.
- [x] Análise semântica exigindo operandos de mesmo tipo e retornando `trit`.
- [x] Lowering correto utilizando `COMPARE` + `BRANCH3` + `STORE`/`LOAD`.
- [x] Execução precisa no emulador e compatibilidade nativa.
- [x] Suíte de testes completa aprovada.
- [x] Documentação e especificações atualizadas.

## Limitações

- Comparação de matrizes inteiras ou estruturas compostas não é suportada (apenas tipos escalares `trit` e `tryte`).

## Checklist

- [x] AST, Lexer e Parser implementados.
- [x] Análise semântica implementada.
- [x] Lowering implementado e verificado contra IR.
- [x] Testes de parser, semântica, lowering e execução criados e aprovados.
- [x] Documentação e especificações sincronizadas.
