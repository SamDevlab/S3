# S3 Milestone 0.42

**Status**: Concluída.

## Objetivos
- Estabelecer a sintaxe e a semântica de loops (`while`).
- Oficializar a sintaxe fonte 0.6 como normativa atual e padrão.
- Marcar explicitamente a sintaxe 0.5 como legado/deprecated.

## Entregas Concluídas

- [x] **While Loop**: Inclusão na gramática da sintaxe 0.6.
- [x] **Semantic Analysis**: Implementação de análise conservadora para o retorno do `while` (a condição constante `-1` executa o corpo, mas o fluxo continua não retornando definitivamente por segurança).
- [x] **Lowering**: O bloco subsequente é isolado e alcançado corretamente após o laço sem gerar dead code ou falhas no pipeline `entry/exit`.
- [x] **Testes**: Cobertura das restrições semânticas e do IR/Assembly emitido.
- [x] **Sintaxe 0.6**: Documentação atualizada (spec e `language.md`) indicando que 0.6 é o default normativo, removendo avisos de "proposta futura".
- [x] **Sintaxe 0.5**: Marcada explicitamente como legada/deprecated em todo o material normativo e instruções de CLI.
- [x] **Self-hosting (estado atual)**: Atualização do `self-hosting.md` confirmando a existência de renderers genéricos em S3 validados contra goldens (`first`, `simple_call`, `sign`), configurando uma prova parcial de viabilidade, enquanto o Python continua como compilador principal.
- [x] **Instrução Nativa**: Limites de instruções no backend experimental nativo `x86-64` marcados como concluídos/implementados nas documentações nativas.
