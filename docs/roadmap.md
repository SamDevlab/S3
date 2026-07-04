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
- limite configurável de 2187 trits por frame;
- CFG, alcançabilidade e dominância SSA;
- comunicação entre ramos sem `PHI`;
- compatibilidade 0.1/0.2 e CI Python 3.11–3.13.

## Marco 0.4 — preparação para backend nativo (recomendado)

1. análise estática de inicialização por caminhos;
2. representação/serialização persistente da IR;
3. ADR de layout físico, stack slots e ABI;
4. encoding de trit/tryte em máquinas binárias;
5. backend x86-64 mínimo para funções escalares;
6. testes diferenciais emulador versus nativo;
7. posteriormente ARM64.

Arrays em assinaturas, heap, ponteiros, strings, módulos e I/O continuam fora
até receberem contratos próprios.

## Autohospedagem

Assembler e frontend em S3 dependem de strings, módulos e uma biblioteca
padrão mínima. Python será removido gradualmente somente após bootstrap
reprodutível.

