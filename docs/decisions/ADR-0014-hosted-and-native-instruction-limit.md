# ADR-0014: limite de instruções hospedado e nativo

- Status: aceito
- Data: 2026-07-05

## Contexto

O emulador hospedado já limita a quantidade de opcodes S3 Assembly executados,
com padrão `100000` e falha estruturada. O runtime Linux x86-64 limita frames,
mas não instruções. Um ciclo estrutural, portanto, termina de forma controlada
no emulador e pode executar indefinidamente no ELF.

O Marco 0.7 precisa fechar essa assimetria sem alterar a linguagem, o conjunto
de opcodes ou os formatos persistentes.

## Problema

Sem uma unidade comum, uma ordem de contagem e uma configuração pública, a
instrumentação nativa poderia contar instruções físicas, helpers ou checks,
divergir do emulador e produzir efeitos parciais depois de esgotar o orçamento.

O1 também pode reduzir a quantidade de opcodes executados. Exigir que O0 e O1
esgotem limites baixos no mesmo ponto confundiria equivalência semântica com
um limite aplicado ao programa já otimizado.

## Decisão

O Marco 0.7 implementará exclusivamente a paridade do limite de instruções
entre o emulador hospedado e o runtime Linux x86-64. Esta ADR formaliza o
contrato; a implementação permanece pendente e começa na E1.

### Unidade e ordem de contagem

Cada opcode S3 Assembly efetivamente executado consome uma unidade. Isso inclui
`TLOAD`, `TSTORE`, `TBR3`, `TJMP`, `TCALL`, `TRET` e todos os demais opcodes
existentes.

Não contam:

- prólogos ou epílogos x86-64;
- helpers internos;
- checks físicos introduzidos pelo backend;
- instruções físicas x86-64;
- syscalls;
- assembler ou linker.

Antes de cada opcode S3:

1. se o contador for igual ao limite, falhar no site do opcode pendente;
2. caso contrário, incrementar o contador uma vez;
3. executar o opcode.

Um limite `N` permite no máximo `N` opcodes concluídos. O opcode `N + 1` não
pode produzir efeitos.

### Contador e default

O contador começa em zero antes de `main`, é global para a execução e é
compartilhado por chamadas e recursão. Ele é independente dos limites de frames
e memória lógica, não é observável ou endereçável pelo programa S3 e não pode
sofrer wraparound antes da comparação.

Emulador e runtime nativo usam o mesmo default:

```text
max_instructions = 100000
```

O valor deve ser inteiro positivo. Zero e valores negativos são inválidos. Não
existe modo ilimitado implícito.

### O0 e O1

O orçamento incide sobre o S3 Assembly efetivamente selecionado depois de O0
ou O1. Limites baixos podem ser esgotados em pontos diferentes porque a
quantidade de opcodes executados pode mudar.

A equivalência entre O0 e O1 permanece obrigatória quando ambas as execuções
terminam dentro do orçamento. Exaustão do limite não autoriza diferença
semântica, corrupção de estado nem execução parcial do opcode excedente.

### CLI e API Python

A implementação acrescentará:

```text
--max-instructions N
```

A opção será aceita somente por:

- `run`, para configurar o emulador;
- `native-asm`, para incorporar o limite à assembly nativa;
- `build`, para incorporá-lo ao artefato nativo;
- `run-native`, para incorporá-lo ao artefato executado.

Os demais comandos devem rejeitar a opção, nunca ignorá-la silenciosamente.

`run_source`, a execução pública de Assembly, `X8664Backend`,
`generate_native_assembly` e, direta ou indiretamente conforme a arquitetura,
`X8664Emitter` devem aceitar o mesmo conceito. A validação ocorre antes da
execução ou emissão. Parâmetros e defaults existentes permanecem compatíveis.

### Diagnósticos

O emulador preserva:

- código `S3E_RUNTIME_INSTRUCTION_LIMIT`;
- categoria `instruction-limit`;
- fase `emulation`;
- status 1 na CLI;
- campo `limit`;
- função, bloco, opcode e origem quando disponíveis.

O runtime nativo acrescentará a categoria textual `instruction limit`, escreverá
em stderr e encerrará com status 1. O diagnóstico informa limite, função,
bloco, opcode e origem quando disponíveis e ocorre antes dos efeitos do opcode
excedente.

Em `run-native --diagnostic-format json`, a CLI continua emitindo
`S3E_NATIVE_PROCESS_FAILED` e preservando o stderr nativo em `notes`. Ela não
interpreta nem converte semanticamente o texto do ELF.

### Versões e compatibilidade

A distribuição destinada ao fechamento do marco será 0.7.0, mas nenhuma versão
muda na E0. Permanecem:

```text
sintaxe fonte       0.6
IR JSON             0.5.0
S3 Assembly         0.5.0
s3-diagnostic       1.0.0
```

O limite é configuração de execução e emissão, não conteúdo serializado. Não
haverá campo novo em IR nem diretiva nova em Assembly.

V0.6 continua sendo a sintaxe padrão. V0.5 permanece disponível somente por
seleção explícita. Não há autodetecção, fallback, segunda tentativa de parser
ou migração implícita. A rejeição de versões futuras permanece inalterada.

Programas que terminam dentro do orçamento preservam os resultados atuais.
Programas nativos que excedem o default passam de execução potencialmente
ilimitada para falha controlada; essa mudança observável está aprovada.

## Fora de escopo

Não integram o Marco 0.7:

- cache de artefatos;
- métricas ou novos passes de otimização;
- novos opcodes, sintaxe, gramática, AST ou semântica da linguagem;
- mudanças de IR, Assembly ou schema diagnóstico;
- ARM64, Windows ou macOS nativos;
- heap, ponteiros, globals, strings, módulos, I/O ou autohospedagem;
- correção do F841 histórico.

## Alternativas rejeitadas

- **Manter o runtime nativo ilimitado:** preserva a assimetria e deixa ciclos
  dependerem de interrupção externa.
- **Modo ilimitado implícito ou default diferente:** quebra a paridade e torna
  a configuração menos previsível.
- **Contar instruções físicas x86-64 ou helpers:** depende do backend e faz um
  opcode S3 ter custo variável por implementação.
- **Falhar depois do opcode excedente:** permite efeitos além do orçamento.
- **Contador por frame:** reinicia o orçamento em chamadas e permite contornar
  o limite por recursão.
- **Exigir o mesmo ponto de exaustão em O0 e O1:** ignora que o orçamento incide
  sobre o Assembly efetivamente otimizado.
- **Aceitar a opção em comandos sem efeito:** cria configuração silenciosamente
  ignorada.
- **Serializar o limite na IR ou Assembly:** altera formatos sem necessidade;
  o limite pertence à execução e à emissão.
- **Interpretar o stderr do ELF na CLI:** tornaria texto humano uma API
  semântica frágil e contrariaria o ADR-0012.

## Consequências

O emulador e o ELF terão a mesma proteção padrão contra execução ilimitada. O
runtime nativo ganhará estado privado e instrumentação por opcode, aumentando
o texto e o custo da execução. Builds continuam determinísticos para a mesma
entrada, configuração e toolchain.

Fonte, frontend, IR e S3 Assembly permanecem semanticamente inalterados. A
mudança observável se restringe a programas nativos que excedem o orçamento e
passam a falhar de forma controlada.

## Riscos

- instrumentação em todos os opcodes pode aumentar tamanho e custo do ELF;
- erro de fronteira pode permitir apenas `N - 1` ou `N + 1` opcodes;
- omitir um opcode ou contar helper quebra a unidade definida;
- o contador deve evitar wraparound antes da comparação;
- limites baixos podem confundir usuários ao terminar em pontos diferentes
  entre O0 e O1;
- metadados do site excedente precisam sobreviver corretamente à otimização;
- a reprodutibilidade deve ser revalidada para cada configuração do limite.
