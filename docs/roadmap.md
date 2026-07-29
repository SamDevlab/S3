# Roadmap do S3

## Marco 0.1 — bootstrap vertical (concluído)

Tipos ternários, frontend inicial, lowering sem subtração, assembly, emulador,
CLI e testes.

## Marco 0.2 — funções e controle ternário (concluído e estabilizado)

Parâmetros, chamadas, recursão, switch exaustivo, IR em blocos, frames e origem.
Na estabilização 0.3, o exemplo normativo foi tornado executável, a EBNF foi
fatorada, a política de ciclos corrigida e CI adicionada.

## Marco 0.3 — memória e agregados mínimos (concluído)

- `mut` e atribuição explícita;
- arrays estáticos `trit`/`tryte`;
- objetos tipados locais ao frame;
- `LOAD`/`STORE`, `.memory`, `TLOAD`/`TSTORE`;
- bounds e inicialização seguros;
- memória independente em recursão;
- limite configurável de 6561 trits (`3^8`) por frame;
- CFG, alcançabilidade e dominância SSA;
- comunicação entre ramos sem `PHI`;
- compatibilidade 0.1/0.2 e CI Python 3.11–3.13.

## Marco 0.4 — backend nativo Linux x86-64 (concluído, experimental)

- representação int8/int16 e cálculos int64 sob ADR;
- layout determinístico de frames, flags e arrays locais;
- System V AMD64 com argumentos adicionais pela pilha;
- todos os opcodes S3 Assembly 0.3, sem `TSUB`;
- helpers tritwise, bounds, inicialização e imutabilidade;
- runtime `_start` sem libc, C, LLVM ou Python;
- CLI `native-asm`, `build` e `run-native`;
- corpus diferencial e todos os exemplos;
- CI nativa obrigatória em Ubuntu x86-64.

## Marco 0.5 — robustez e otimização inicial (concluído e validado)

Validado pelo GitHub Actions no commit `70d10a0`, com sucesso em:

- Python 3.11;
- Python 3.12;
- Python 3.13;
- backend nativo Linux x86-64.

Entregas validadas na execução remota acima:

- correção de entrada física no bloco `entry`;
- limite nativo configurável de frames;
- diagnósticos com função, bloco, opcode, origem e valor;
- S3 Assembly e IR JSON versionadas em 0.5.0;
- round-trip e verificação estrita de IR;
- análise conservadora de inicialização;
- O0 padrão e O1 local com verificação dupla;
- testes de ELF reproduzível na mesma toolchain;
- diferenciais O0/O1 emulador/nativo;
- estudo ARM64 sem backend ou alegação de suporte.

## Marco 0.6 — primeiro MVP publicável (concluído e validado)

Escopo concluído e validado antes da Entrega E:

- diagnósticos estruturados consumíveis por ferramentas na CLI hospedada;
- schema `s3-diagnostic` 1.0.0, com categorias e códigos estáveis;
- formato textual preservado como padrão;
- fronteira explícita: o runtime ELF continua com diagnósticos textuais.
- simplificação da sintaxe de fonte (ADR-0013):
  - Entrega A concluída e validada;
  - Entrega B concluída e validada;
  - Entrega C1 concluída e validada;
  - Entrega C2 concluída e validada;
  - Entrega D1 concluída;
  - Entrega D2A concluída;
  - Entrega D2A.1 concluída;
  - Entrega D2B concluída e validada;
  - V0.6 é o default do frontend e da CLI;
  - V0.5 continua disponível por seleção explícita, sem fallback;
  - corpus oficial migrado para V0.6.

Entrega E:

- fechamento do contrato do MVP e da versão pública 0.6.0;
- auditoria de instalação, empacotamento, CLI, exemplos e artefatos;
- notas de lançamento preparadas;
- concluída e validada no commit
  `aceee820ebc99b7d90fc5d32dd8fa8e699ad37b5`;
- GitHub Actions
  [`28737520765`](https://github.com/SamDevlab/S3/actions/runs/28737520765)
  verde em Python 3.11–3.13 e Linux x86-64 nativo;
- Marco 0.6 concluído.

## Marco 0.7 — paridade do limite de instruções (concluído)

A E0 aprovou o contrato normativo do limite de instruções. A E1 implementou
a paridade hospedada. A E2 implementou a instrumentação nativa. O contrato está no
[ADR-0014](decisions/ADR-0014-hosted-and-native-instruction-limit.md) e no
[plano do marco](milestone-0.7.md).

Estado:

- E0, decisão normativa: concluída;
- E1, paridade hospedada e interface pública: concluída;
- E2, instrumentação nativa: concluída;
- E3, validação ELF: concluída;
- E4, fechamento: concluída; versão 0.7.0, tag e release publicadas.

O que a E1, E2 e E3 entregaram:

- `DEFAULT_MAX_INSTRUCTIONS = 100_000` como constante pública em `emulator.py`;
- `max_instructions` exposto em `run_source`, `execute_assembly` e `generate_native_assembly`;
- `s3 run`, `native-asm`, `build` e `run-native` aceitando `--max-instructions N` com validação de valores inválidos;
- contador de instruções e falhas estruturadas instrumentadas no backend x86-64;
- diagnóstico `S3E_RUNTIME_INSTRUCTION_LIMIT` hospedado preservado sem alteração;
- validação ELF real O0/O1, controle de fluxo e chamadas, e preservação da faixa u64 nativa.

O default aprovado é `100000` opcodes S3 Assembly executados. Fonte, gramática,
AST, semântica, IR 0.5.0, Assembly 0.5.0 e schema diagnóstico 1.0.0 não mudam.
Nenhuma outra funcionalidade foi incorporada.

## Marco 0.8 — Medição e desempenho orientado por evidências

O Marco 0.8 foi iniciado exclusivamente em nível normativo. A infraestrutura de benchmark, medição estruturada de O0/O1 e execução paralela do ELF visam embasar dados empíricos precisos antes de implementar qualquer otimização adicional na base semântica da linguagem S3.

Estado atual:

- E0, contrato normativo: concluída e integrada;
- E1, workloads e runner no mesmo processo: concluída e integrada;
- E2, tempos por fase e métricas determinísticas: implementada no Draft PR #4, aguardando revisão e integração;
- E3, CLI e ELF Linux x86-64: futura;
- E4, diagnóstico de gargalo: futura;
- E5, otimização dirigida por evidência: futura;
- E6, fechamento (sem versão 0.8.0 publicada ainda): futura.

Nenhum outro benchmark ou otimização foi implementado ainda.

## Pós-MVP / marcos futuros

Não integram o Marco 0.7 e não estão implementados:

1. cache de artefatos por conteúdo/versionamento;
2. métricas e orçamento de otimização por exemplo;
3. otimizações entre blocos provadas sem `PHI`;
4. backend ou execução ARM64 experimental.

Arrays em assinaturas, heap, ponteiros públicos, strings dinâmicas, módulos e
I/O continuam fora do MVP até receberem contratos próprios. O Marco 0.53 cobre
valores `string` estáticos tipados, e o Marco 0.54 adiciona concatenação
estática literal-only em tempo de compilação. O Marco 0.55 estende `len(...)`
para calcular comprimento de texto estático em tempo de compilação. O Marco
0.56 adiciona igualdade e desigualdade de texto estático em tempo de
compilação. O Marco 0.57 permite propagar texto estático por bindings
imutáveis locais. O Marco 0.58 adiciona indexação de texto estático em tempo
de compilação com índices literais.

## Autohospedagem

Assembler e frontend em S3 dependem de strings além de concatenação estática
literal-only, comprimento estático, igualdade estática, propagação por
bindings imutáveis, indexação estática de texto, módulos e uma biblioteca
padrão mínima. Python será removido gradualmente somente após bootstrap
reprodutível.
