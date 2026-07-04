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

Implementado localmente; conclusão remota depende do job CI após push:

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

## Marco 0.6 — robustez operacional (iniciado)

Primeira entrega implementada:

- diagnósticos estruturados consumíveis por ferramentas na CLI hospedada;
- schema `s3-diagnostic` 1.0.0, com categorias e códigos estáveis;
- formato textual preservado como padrão;
- fronteira explícita: o runtime ELF continua com diagnósticos textuais.

Permanecem pendentes:

1. cache de artefatos por conteúdo/versionamento;
2. métricas e orçamento de otimização por exemplo;
3. política de limite nativo de instruções;
4. otimizações entre blocos provadas sem `PHI`;
5. execução ARM64 experimental somente após ADR/backend/runtime/CI completos.

Arrays em assinaturas, heap, ponteiros, strings, módulos e I/O continuam fora
até receberem contratos próprios.

## Autohospedagem

Assembler e frontend em S3 dependem de strings, módulos e uma biblioteca
padrão mínima. Python será removido gradualmente somente após bootstrap
reprodutível.
