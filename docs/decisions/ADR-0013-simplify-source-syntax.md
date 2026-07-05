# ADR 0013: Simplify source syntax with indentation-based blocks

## Status

Aceita e implementada para a fonte V0.6. O MVP mantém V0.5 apenas por seleção
explícita, sem autodetecção ou fallback. Essa compatibilidade transitória
substitui a previsão original de remoção imediata da gramática antiga na
Entrega D; não altera a gramática V0.6 nem os formatos posteriores.

## Contexto
O S3 iniciou com uma sintaxe baseada em chaves (`{}`) e ponto e vírgula (`;`). Isso permitiu focar rapidamente na semântica, infraestrutura, IR e assembly. No entanto, à medida que avançamos para o Marco 0.6, o objetivo é alinhar a sintaxe com a filosofia central "Menos é mais", garantindo uma experiência ergonômica, de baixa cerimônia, mas sem perder as garantias estáticas de uma linguagem de sistemas.

## Problema
A sintaxe atual possui ruído visual desnecessário (chaves, ponto e vírgula). O construto `switch` também não reflete com exatidão a natureza estrita e sem fallthrough do fluxo de controle ternário do S3. A multiplicidade de formas de binding mutável e imutável pode levar a ambiguidades no parsing se a inferência for usada livremente sem depender do analisador semântico.

## Objetivos
- Simplificar a sintaxe mantendo um parser LL(1) pequeno.
- Eliminar chaves e ponto e vírgula.
- Propor uma sintaxe de declaração e atribuição explícita e não ambígua.
- Migrar de `switch` para `match`.
- Preparar a especificação para a implementação no compilador (Milestone 0.6).

## Não objetivos
- Não introduzir tipagem dinâmica.
- Não alterar semântica de tipos ou memória.
- Não introduzir operadores compostos (`+=`).
- Não alterar IR, Assembly, ABI ou backends nesta etapa.
- Não manter permanentemente suporte à sintaxe antiga após a migração.

## Decisão Proposta
1. **Blocos e Indentação:** Blocos lógicos começam após `:` e são delimitados por tokens lógicos `INDENT` e `DEDENT`. Declarações terminam com `NEWLINE`.
2. **Declarações e Atribuições:** `name: type = expr` declara um binding imutável. `mut name: type = expr` declara um binding mutável. `name = expr` é exclusivamente uma atribuição e só pode atingir um binding mutável previamente declarado. Não há `let`, `var` ou `:=`.
3. **Mutabilidade:** Continua explícita através da keyword `mut` combinada com o tipo (`mut name: type = expr`).
4. **Controle de Fluxo:** Substituir `switch` por `match`.
5. **Expressões Multilinha:** Quebra livre permitida dentro de `()`, `[]`. O newline fora destes caracteres encerra a instrução.
6. **Comentários:** Manter `#` como forma única (alterado de `//` para se alinhar com a preferência estilística adotada).

## Alternativas rejeitadas
- **Inserção Automática de Semicolon (ASI):** Rejeitado pela complexidade do parser e comportamento surpreendente.
- **Inferência local e keywords (`let`/`var`/`:=`):** Totalmente rejeitadas. Formas como `value = 5` ou `mut counter = 0` são inaceitáveis como declarações. A obrigatoriedade da anotação de tipo em novas declarações mantém a gramática LL(1) simples e pura. Não existe inferência local, global ou interprocedural nesta versão.
- **Operadores compostos (`+=`):** Rejeitado. Mantemos `a = a + 1` para não esconder semânticas de sistema (overflow, mutabilidade).

## Impacto no frontend
- O `Lexer` precisará manter o rastreio da profundidade da indentação emitindo `NEWLINE`, `INDENT` e `DEDENT`.
- O `Parser` consumirá esses tokens lógicos em substituição a `{`, `}` e `;`.

## Impacto na compatibilidade e Estratégia de Migração
A sintaxe sofrerá uma quebra (breaking change) no source do projeto, porém IR e Assembly permanecerão compatíveis (versão 0.5.0). Para não manter o peso de dois parsers permanentemente, a estratégia será a substituição direta. Erros de parsing claros e amigáveis (aproveitando o sistema de diagnósticos estruturados) serão emitidos se `;` ou `{}` forem encontrados, instruindo o desenvolvedor a migrar.

## Consequências
Uma base sintática ergonômica que reduz as linhas de código e símbolos de pontuação, mantendo-se estática e apta para evolução de baixo nível (arrays, ponteiros, layouts) no futuro.

## Plano de implementação (Etapas)
1. **Entrega A — Infraestrutura de indentação:** Lexer lida com NEWLINE, INDENT, DEDENT; testes de lexer.
2. **Entrega B — Funções e instruções simples:** Remoção de ponto e vírgula e chaves, implementação do return e parsing de declarações e atribuições sem ambiguous states.
3. **Entrega C — Construções compostas:** Parsing de match, arrays, regras de multiline.
4. **Entrega D — Migração:** Conversão de scripts `.s3` e testes legados, remoção completa da gramática antiga.
5. **Entrega E — Validação final:** Garantia do pipeline e diagnósticos estruturados funcionando com a nova gramática.
