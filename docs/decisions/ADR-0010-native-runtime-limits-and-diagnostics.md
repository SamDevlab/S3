# ADR-0010: limites e diagnósticos do runtime nativo

- Status: aceito
- Data: 2026-07-03

## Contexto

Depender do stack overflow do sistema torna recursão excessiva imprevisível. As
mensagens 0.4 indicam categorias, mas não localizam função, bloco ou origem.
Ambos são requisitos de segurança do runtime, não novas variáveis da linguagem.

## Limite de frames

O padrão é `max_frames = 1024`, configurável na API e CLI. Uma célula de 64
bits em `.bss`, privada sob o prefixo `__s3_`, conta somente entradas em funções
S3. `_start` e helpers não contam.

Antes de alocar o frame físico, cada função incrementa o contador e compara com
o limite embutido no assembly. Excesso termina por erro controlado antes de
consumir outro frame. Cada `TRET` decrementa exatamente uma vez. Erros não
desempilham porque encerram o processo. Frame lógico e quantidade de bytes de
stack são conceitos distintos.

## Diagnósticos

Pontos de falha recebem IDs inteiros em ordem determinística de
função/bloco/instrução/check. Nenhum ID depende de hash, endereço ou path.
Metadados estáticos incluem:

```text
categoria, função, bloco, opcode, linha assembly, origem S3
```

O formato compacto é:

```text
runtime error [category] in function 'name'
at source L:C (block label, OPCODE): detail
```

Assembly manual sem origem imprime `source unknown`; nunca inventa posição.
Quando relevante, `detail` contém o valor dinâmico, como índice, resultado ou
limite. Strings e conversão decimal vivem no runtime assembly, sem libc, C ou
Python.

Categorias mínimas: `overflow`, `bounds`, `uninitialized register`,
`uninitialized memory`, `immutable memory`, `invalid trit state`,
`frame limit` e `invalid runtime state`. Erros escrevem em stderr e usam status
1. Sucesso continua em stdout e status 0.

## Consequências

O assembly cresce por manter tabelas locais, uma escolha intencional em favor
de diagnóstico auditável. O contador é estado de implementação inacessível ao
S3 e não introduz memória global na linguagem.

