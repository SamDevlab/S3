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

## Marco 0.5 — robustez e otimização inicial (recomendado)

1. análise estática de inicialização por caminhos;
2. representação/serialização persistente e versionada da IR/assembly;
3. testes reprodutíveis de bytes ELF entre toolchains suportadas;
4. eliminação local de movimentos e slots comprovadamente desnecessários;
5. diagnósticos nativos com função/origem preservadas;
6. política nativa explícita para profundidade de recursão;
7. avaliação separada de um backend ARM64, sem marcá-lo como suportado antes
   de ADR, runtime e CI próprios.

Arrays em assinaturas, heap, ponteiros, strings, módulos e I/O continuam fora
até receberem contratos próprios.

## Autohospedagem

Assembler e frontend em S3 dependem de strings, módulos e uma biblioteca
padrão mínima. Python será removido gradualmente somente após bootstrap
reprodutível.
