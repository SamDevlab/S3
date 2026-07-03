# ADR-0001: arquitetura do bootstrap

- Status: aceito
- Data: 2026-07-03

## Contexto

S3 precisa validar sua semântica antes que exista um compilador S3, mas não pode
depender permanentemente de uma VM ou linguagem hospedeira. Também é necessário
evitar que AST, IR e assembly se tornem uma única representação difícil de
substituir.

## Decisão

Usar Python 3.11 e somente sua biblioteca padrão no runtime como implementação
temporária, confinada a `bootstrap/`. Separar lexer, AST, análise semântica, IR,
assembly e emulador por modelos explícitos. Manter a especificação em `spec/`
como autoridade e reservar `selfhost/` para código futuro em S3.

Implementar em fatias verticais testáveis. A primeira termina em um emulador de
registradores e não tenta gerar código nativo.

## Alternativas consideradas

- Implementar diretamente em S3: impossível antes de existir toolchain.
- Usar LLVM desde o início: acrescentaria uma dependência grande e anteciparia
  decisões de backend antes da semântica ternária estar estável.
- Interpretar diretamente a AST: seria menor, mas não validaria as fronteiras
  de IR, assembly e lowering exigidas para autohospedagem.
- Compartilhar uma estrutura genérica entre todas as etapas: reduziria código,
  mas permitiria dependências acidentais e subtração sobreviver ao lowering.

## Consequências

Há alguma duplicação deliberada de enums e tipos entre camadas. Em troca, cada
artefato é inspecionável, substituível e testável. Python permanece um oráculo,
não parte da arquitetura final. Futuras implementações devem reproduzir os
testes normativos antes de substituir uma etapa.

