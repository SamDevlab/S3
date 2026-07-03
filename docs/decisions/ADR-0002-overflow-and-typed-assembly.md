# ADR-0002: overflow detectável e assembly tipada

- Status: aceito
- Data: 2026-07-03

## Contexto

Um tryte tem faixa pequena e operações podem sair dela. Wraparound silencioso
esconderia defeitos no bootstrap. O emulador também precisa distinguir um
registrador `trit` de um `tryte` sem depender de metadados privados do
compilador.

## Decisão

Tratar toda constante ou resultado fora da faixa como erro. Literais são
validados estaticamente; valores de assembly e resultados aritméticos são
validados a cada escrita.

Declarar tipos de registrador no texto:

```asm
.register r0, tryte
```

As instruções verificam compatibilidade de operandos e `TCMP` exige destino
`trit`. Não existe promoção automática.

## Alternativas consideradas

- Wraparound módulo 729: eficiente e potencialmente útil em hardware, mas
  silencioso e prematuro.
- Saturação: determinística, porém altera identidades aritméticas.
- Tipos codificados no nome do opcode: multiplicaria instruções e tornaria o
  conjunto menos minimalista.
- Tipos disponíveis apenas na IR: faria o assembly textual depender do
  compilador para ser executado com segurança.

## Consequências

Programas com overflow terminam com diagnóstico compreensível. A assembly é
mais verbosa, mas autocontida. A política pode ser revisada no futuro por uma
nova versão da especificação e opcode/modo explícito; nunca por mudança
silenciosa de comportamento.

