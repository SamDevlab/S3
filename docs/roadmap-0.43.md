# S3 Milestone 0.43 — Loop Control-Flow Jump Statements

**Status**: completed

## Objetivos

Adicionar suporte às instruções de desvio e controle de fluxo de laço `break` e `continue` na sintaxe fonte S3 0.6, exclusivamente para uso dentro de laços `while`.

## Motivação

Permitir o encerramento antecipado de iterações e o salto direto para a reavaliação de condição em laços `while`, aumentando a expressividade da linguagem sem adicionar complexidade à representação intermediária (IR).

## Contrato

- Sintaxe: `break` e `continue` como statements autônomos (sem rótulos, labels ou expressões).
- Validade: Exclusivamente dentro de corpos de `while`.
- Escopo de desvio: Sempre associado ao laço `while` mais interno.
- Lowering: `break` desce para `JUMP while_exit` e `continue` desce para `JUMP while_condition`. Zero opcodes IR novos.
- Código inalcançável: Statements no mesmo bloco após `break` ou `continue` são rejeitados na compilação.
- Definite-return: `break` e `continue` encerram o fluxo local do bloco, mas não satisfazem o retorno de função. A análise de retorno de função permanece conservadora.

## Escopo

- Definição dos tokens `BREAK` e `CONTINUE` em `lexer.py` na sintaxe V0.6 (mantendo V0.5 inalterada).
- Definição dos nós AST `BreakStatement` e `ContinueStatement` em `ast.py`.
- Suporte a parsing no `parser.py` para a sintaxe V0.6 com terminação por `NEWLINE`.
- Travessia segura em `static_strings.py`.
- Validação no `semantic.py` com rastreamento de `loop_depth` e modelo `BlockFlow` para detecção de dead code.
- Lowering no `lowering.py` utilizando pilha interna `loop_stack`.
- Suíte completa de testes de parser, semântica, lowering e execução.

## Não Escopo

- Novos opcodes de IR.
- Laços `for`.
- Rótulos/labels ou argumentos de expressão em `break`/`continue`.
- Alterações na sintaxe V0.5 legada.
- Alterações na suíte de goldens ou opcodes do backend nativo.

## Arquitetura

- **Lexer**: `TokenKind.BREAK` e `TokenKind.CONTINUE` reconhecidos se `mode == SyntaxMode.V0_6`.
- **AST**: `BreakStatement` e `ContinueStatement` estendem a união `Statement`.
- **Parser**: Consumo de tokens `BREAK` e `CONTINUE` exigindo `NEWLINE`.
- **Semântica**: Rastreamento `self.loop_depth` no analisador semântico e classe `BlockFlow(terminates, definitely_returns)`.
- **Lowering**: Pilha `self.loop_stack: list[LoopContext]` empilhando `LoopContext(continue_target, break_target)` durante `_lower_while`.

## Testes

- `tests/test_s3_while_parser.py`: Cobertura de parsing válido, inválido (parâmetros, `:`, v0.5).
- `tests/test_s3_while_semantic.py`: Cobertura de uso fora de laço, `match` em `while`, código inalcançável, retorno obrigatório.
- `tests/test_s3_while_lowering.py`: Cobertura de alvos `JUMP`, eliminação de dead code no lowerer e laços aninhados.
- `tests/test_s3_while_execution.py`: Programas de teste com `break`, `continue` e laços aninhados executados no emulador.

## Critérios de Aceitação

- [x] Parsing de `break` e `continue` na sintaxe V0.6 sem argumentos.
- [x] Validação semântica rejeitando o uso fora de `while`.
- [x] Rejeição de código inalcançável no mesmo bloco após `break` e `continue`.
- [x] Lowering correto para `JUMP` visando o laço mais interno.
- [x] Suíte de testes aprovada.
- [x] Especificação (`spec/grammar.ebnf`, `spec/source-syntax-0.6.md`, `spec/language.md`) e `README.md` sincronizados.

## Limitações

- `break` e `continue` atuam somente sobre o laço `while` mais interno. Salto multi-nível via labels não é suportado nesta versão.

## Checklist

- [x] AST, Lexer e Parser implementados.
- [x] Análise semântica implementada.
- [x] Lowering implementado.
- [x] Testes de parser, semântica, lowering e execução adicionados.
- [x] Documentação e especificações atualizadas.
