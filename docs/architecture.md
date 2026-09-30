# Arquitetura do S3 bootstrap 0.5

## Pipeline

```text
fonte → lexer → AST → semântica
      → lowering SSA + objetos de memória
      → IR com CFG/dominância verificada
      → análise de inicialização → otimização O0/O1 → nova verificação
      → S3 Assembly 0.6 tipada, versionada e validada
        ├→ emulador com frames e memória local
        └→ backend x86-64 → GNU assembly → ELF Linux
```

AST, semântica, IR e assembly permanecem modelos separados. Origem atravessa
camadas por `SourceLocation`.

## Frontend

A AST distingue tipo escalar/array, literal de array, indexação, mutabilidade e
alvos de atribuição. A tabela semântica associa a cada binding tipo,
mutabilidade, origem e condição de parâmetro.

Arrays fixos `trit`/`tryte` entram em assinaturas como grupos de células
derivados de `SemanticModel.fixed_value_layout(...)`. A passagem é copy-by-value
e não expõe endereços. Bounds de expressões constantes simples (`literal`,
negação, soma/subtração) são checados estaticamente; demais índices chegam ao
emulador.

## Lowering híbrido

- escalar imutável: registrador SSA;
- escalar `mut`: objeto de memória de comprimento 1;
- array local: objeto de memória do comprimento declarado;
- array em boundary: grupo escalar completo em ordem crescente de índice;
- leitura: `LOAD`;
- inicialização/atribuição: `STORE`;
- índices e valores: registradores SSA.

Em switch, ramos armazenam no mesmo objeto preexistente e o join carrega o
valor. Não há `PHI`.

## CFG e dominância

O verificador valida todos os blocos, constrói arestas dos terminadores, calcula
alcançabilidade e dominadores por ponto fixo. Uma definição deve preceder o uso
no bloco ou dominar o bloco consumidor. Isso rejeita valores originados em
apenas um ramo e usados no join.

Ciclos são permitidos. A análise não prova terminação; o emulador aplica limite
global configurável de instruções.

## Inicialização e O1

O passe de inicialização calcula ponto fixo por elemento com estados
`UNINITIALIZED`, `INITIALIZED` e `MAYBE_INITIALIZED`. Load constante
definitivamente inválido e segunda inicialização imutável comprovada são erros
estáticos. Índices dinâmicos e joins incertos mantêm checks de runtime.

O0 preserva a IR. O1 dobra/propaga constantes locais, remove resultados puros
seguros e mortos, blocos inalcançáveis e trampolins de salto. ADD potencialmente
overflow, efeitos e terminadores não são apagados. Verificador e análise rodam
antes e depois.

## Arquitetura interna do otimizador SSA

O otimizador O1 usa SSA apenas como representacao interna. A fachada historica
`bootstrap.s3.ssa_opt` permanece estavel para o compilador e testes existentes,
mas as responsabilidades internas ficam separadas em `bootstrap.s3.ssa_optimizer`.

Os limites atuais sao:

- `contracts.py`: contratos, inventario O1 e `PassResult`;
- `common.py`: helpers compartilhados;
- `lowering.py`: SSA para IR e CFG reconstruido de blocos SSA;
- `propagation.py`: propagacao de constantes e copias;
- `value_numbering.py`: CSE e GVN;
- `elimination.py`: DCE, ADCE e DSE;
- `loops.py`: LICM e strength reduction;
- `sccp.py`: propagacao condicional esparsa;
- `peephole.py`: reescritas locais.

A convergencia do fixpoint continua baseada em mudanca estrutural real na SSA
retornada. Contadores alimentam telemetria, mas nao sao prova de convergencia
nem autorizam transformacoes que a estrutura retornada nao realizou.

## Loop-carried recurrence facts (S3 1.12)

`analyze_loop_facts` now records a scalar induction or reduction only when the
loop has one initializing preheader, the scalar storage does not escape, each
loop-local store matches the same typed recurrence, and every abstractly
reachable backedge carries exactly one update. The path walk includes multi-
block continuations and does not use a function-wide store count, so sequential
loops may safely reuse a scalar after reinitialization.

These facts do not by themselves prove vector access bounds or general memory
independence and do not authorize SIMD or code-generation changes. Ordered f64
reductions are reported as `NOT_VECTORIZABLE` when reassociation would violate
strict floating-point order; other loops remain `UNKNOWN` until their missing
range, alias, and call-effect proofs are available. Unknown or mutating calls
are surfaced explicitly in the legality report.

## Artefatos

S3 Assembly usa `.s3asm 0.7.0`; texto legado 0.6.0 e 0.5.0 é normalizado. IR
persistente usa JSON `s3-ir` 0.6.0 canônica, estrita e terminada por newline.
Desserialização reconstrói modelos explícitos, normaliza artefatos 0.5 width-1
para `result_types`/`results` explícitos e chama `verify_ir`.

## Assembly e memória por frame

`.memory` torna objetos autocontidos no texto. `TLOAD`/`TSTORE` não manipulam
endereços, apenas identidade de objeto e índice.

Ao criar um `Frame`, o emulador:

1. copia parâmetros para registradores;
2. aloca lista independente de células não inicializadas por objeto;
3. verifica custo contra `max_memory_trits`;
4. executa bounds, tipo e inicialização em cada acesso;
5. descarta memória ao retornar.

Defaults:

```text
max_frames        = 1024
max_instructions  = 100000
max_memory_trits  = 6561
```

## Limite de instruções do Marco 0.7

O [ADR-0014](decisions/ADR-0014-hosted-and-native-instruction-limit.md) estendeu e implementou o
default `max_instructions = 100000` ao runtime Linux x86-64, atingindo paridade no Marco 0.7.

Cada opcode S3 Assembly efetivamente executado consumirá uma unidade. Antes do
opcode, o runtime verificará o limite, incrementará o contador uma vez e só
então executará o opcode. O contador será global para a execução, compartilhado
por chamadas e recursão e independente de frames e memória lógica. Instruções
x86-64, helpers, checks, prólogos, epílogos e syscalls não serão contados.

O orçamento incidirá sobre o S3 Assembly posterior a O0 ou O1. Limites baixos
podem terminar em pontos diferentes; execuções que terminarem dentro do
orçamento continuarão semanticamente equivalentes.

## Backend nativo

`backends/x86_64` consome apenas `AssemblyProgram` validado pelo limite público
do emulador. O layout é uma etapa isolada: registradores ordenados recebem
slots de 8 bytes e flags; objetos ordenados recebem regiões int8/int16 e flags
por elemento; regiões não se sobrepõem e o frame termina alinhado a 16 bytes.

O emitter mantém todos os valores virtuais no frame e usa registradores AMD64
como temporários. Funções seguem System V: seis argumentos em registradores,
demais na pilha, retorno em `RAX`. O runtime assembly fornece `_start`,
conversão decimal, helpers tritwise, `write`, `exit` e falhas controladas. A
toolchain detecta Linux x86-64 e invoca `cc`/`gcc`/`clang` sem shell, com
temporários isolados.

Toda função incrementa um contador privado antes de alocar stack e falha ao
exceder `max_frames`; cada `TRET` decrementa. Após o prólogo há salto explícito
para `entry`, independente da ordem física. Pontos de falha recebem IDs
determinísticos e strings com categoria, função, bloco, opcode e origem;
índices e resultados são impressos dinamicamente sem libc.

```text
S3 lógico: trit=1 trit, tryte=6 trits, cota=6561/frame
x86-64 físico: trit=int8, tryte=int16, valores temporários=int64
```

Essas medidas são independentes: flags, padding e slots físicos não consomem a
cota lógica.

## Invariantes

1. Sem conversões implícitas ou overflow silencioso.
2. `-1` continua dois tokens.
3. Imutáveis escalares permanecem SSA.
4. Memória é local, tipada, sem aliasing e sem endereço exposto.
5. Nenhuma leitura não inicializada retorna valor.
6. Bounds nunca são silenciosos.
7. Codegen consome somente IR verificada.
8. Não existem `PHI`, `SUBTRACT`, `TSUB`, ponteiros ou casts.
9. Python continua apenas compilador bootstrap; o ELF não depende dele.
10. Emissão textual, símbolos e offsets são determinísticos.
11. O0 é padrão; O1 não remove falhas semânticas observáveis. O orçamento de
    instruções incide sobre o Assembly resultante, conforme o ADR-0014.
12. Artefatos desconhecidos são rejeitados, nunca adivinhados.

## AssemblyVerifier e validação de desenvolvimento

`bootstrap.s3.assembly_verifier.AssemblyVerifier` é a fonte compartilhada de
validação estrutural de S3 Assembly. Ele não executa programas nem aplica
limites de estado de runtime. O `Emulator` delega sua API pública `validate`
ao verificador e continua responsável pela execução; o backend x86-64 valida
diretamente pelo mesmo objeto antes de emitir código nativo. O renderer apenas
produz a representação textual.

O1 expõe `verify_each_pass=True` para validação de desenvolvimento. O job
dedicado `ssa-per-pass-verification` da CI ativa essa verificação depois de
cada passe e identifica o passe que violou uma invariante. O padrão normal
continua desligado para preservar o custo e o comportamento do caminho de
execução comum.

## Status do MemorySSA e limite arquitetural

A infraestrutura `bootstrap.s3.memory_ssa.MemorySSA` define as estruturas de dados
`MemoryDef`, `MemoryUse`, `MemoryPhi` e `MemorySSA`. Seu status atual é um
**protótipo experimental e parcial**:

- **Current status**: O método `MemorySSA.build` realiza apenas uma varredura
  linear sobre as instruções dos blocos (`ssa_fn.blocks`), gerando versões
  locais simples `m{index}_v{v}`.
- **Known limitations**: Os parâmetros `cfg` (ControlFlowGraph) e `dom_tree`
  (DominatorTree) são reservados na interface, mas não são consumidos pela
  varredura linear atual. A estrutura `MemoryPhi` está definida no modelo, mas
  **não é construída em pontos de junção (join points) do CFG**.
- **Production usage**: As otimizações de produção (`bootstrap.s3.ssa_opt` e
  `bootstrap.s3.ssa_optimizer`) **não dependem do MemorySSA**. Elas operam
  diretamente sobre a IR escalar e verificações de índice de memória.
- **Completion criteria**: Para promover o MemorySSA a um componente completo,
  serão necessários:
  1. Propagação de definições de memória ciente de CFG e dominância;
  2. Construção e inserção de `MemoryPhi` nas fronteiras de dominância;
  3. Tratamento de backedges em laços;
  4. Testes de cobertura cobrindo junções, laços e múltiplos mutadores;
  5. Validação estrutural dedicada antes de qualquer adoção pelo otimizador.
- **Non-goals**: Esta definição arquitetural não introduz ponteiros, heap,
  análise de escape ou alocador de registradores nativos.

## Riscos

Todos os objetos lexicais da função são alocados ao entrar no frame, inclusive
os de ramos não executados; é simples e conservador, mas pode superestimar
memória. Inicialização de memória imutável é verificada dinamicamente na
assembly. O layout x86-64 ainda não aloca registradores. O limite de frames e
o limite de instruções (implementado no Marco 0.7) são verificados ativamente no runtime.
A futura infraestrutura de medição do Marco 0.8 analisará gargalos precisos por
trás desse pipeline antes que ele sofra grandes refatoramentos de otimização.
Não há heap, aliasing ou promoção memória-para-SSA. Reprodutibilidade binária
vale somente na mesma toolchain. Outros targets exigem backend/ADR próprios.

## Reproducible benchmark boundary

The benchmark subsystem is an engineering consumer of the compiler and runtime,
not part of the language semantics or public CLI. ADR-0026 defines the
`s3bench 1.0.0` lifecycle and result schema. Its phase order is discover, build,
verify, warmup, calibrate, measure, summarize, export, compare, and report.

Correctness is a hard boundary: a failed build, timeout, truncated output,
nonzero command status, absent checksum, or checksum mismatch prevents measured
samples and ranking. Durations use `time.perf_counter_ns()`. Warmup and
calibration observations are discarded; final raw samples are retained and
summarized without automatic outlier removal.

The subsystem records compile, link, process, kernel, startup, end-to-end,
artifact-size, and optional memory fields separately. Unavailable values remain
`null`. It invokes external commands as argument lists without a shell and
excludes personal paths, hostnames, usernames, environment dumps, and secrets
from result metadata.

The 0.8 E2 deterministic baseline remains immutable historical evidence. Shared
CI may execute short functional smoke cases but cannot establish authoritative
performance. Native cross-language claims require one controlled Linux
environment with identical inputs, checksums, and complete toolchain metadata.

## Native register allocation foundation

Milestones 1.20–1.22 established CFG-aware liveness and deterministic physical
allocation for the Linux x86-64 backend. The current `X8664Backend` enables
register allocation by default; callers can explicitly set
`register_allocation=False` to retain the stack-backed diagnostic path.

- **ABI System V AMD64**: The backend targets the standard System V AMD64 ABI on Linux.
- **Physical Register Classes**: Registers are categorised as:
  - Stack Pointer: `rsp` (non-allocatable)
  - Frame Pointer: `rbp` (non-allocatable)
  - Return Register: `rax`
  - Argument Registers: `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`
  - Caller-Saved Registers: `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8`, `r9`, `r10`, `r11`
  - Callee-Saved Registers: `rbx`, `rbp`, `r12`, `r13`, `r14`, `r15`
  - Emitter Scratch Registers: `rax`, `r10`, `r11`
- **Allocatable Pool**: The deterministic pool is `rbx`, `r12`, `r13`, `r14`, `r15`, `rdi`, `rsi`, `rdx`, `rcx`, `r8`, and `r9`. `PER_INSTRUCTION` mode reserves `r15` for its logical budget counter when that counter is register-resident.
- **Scratch/Reserved Policy**: `rsp` and `rbp` are always reserved and non-allocatable. `rax`, `r10`, and `r11` are scratch registers reserved for the emitter. No register may belong to both the allocatable pool and reserved/scratch registers.
- **Liveness Equations**: CFG-aware backwards register liveness analysis is performed on S3 Assembly. Successors of blocks are determined by terminators (`TJMP`, `TBR3`, `TRET`). Block equations are:
  - `live_out[B] = ∪ live_in[S]` for all successors `S`
  - `live_in[B] = use[B] ∪ (live_out[B] - def[B])`
  Iterated until a fixed point is reached. Within blocks, instruction equations are:
  - `live_before[I] = uses[I] ∪ (live_after[I] - defs[I])`
- **TCALL/Live-Across-Call**: Registers live across call instructions are identified as `live_before(call) ∩ live_after(call)`, excluding registers defined/returned by the call itself.
- **Initialization Validity vs Liveness**: Value liveness (`REGISTER_VALUE_LIVENESS`) is distinct from variable initialization validity (`REGISTER_INITIALIZATION_VALIDITY`). Allocation and code generation preserve observable uninitialized-register checks and logical initialization metadata.
- **Stack Fallback**: Virtual registers that cannot be assigned a physical color remain in their logical frame slots; residency is whole-function, with no interval splitting or general dynamic spilling.
- **Production Status**: The default native backend uses the deterministic allocator and its call-aware policies. Stack-backed generation is available by explicit configuration.

## Deterministic physical register allocation

Milestone 1.21 implements deterministic physical register allocation on top of the System V AMD64 contract.

- **Interference Graph**: Built using undirected edges between virtual registers. An edge is added between any two registers simultaneously live before or after any instruction. Furthermore, each defined register `d` in `defs[I]` interferes with all registers `la` in `live_after[I]` (except itself), protecting against clobbers from dead definitions.
- **Greedy Coloring**: Order-determined greedy coloring assigns physical registers. Nodes are sorted primarily by degree descending, and secondarily by virtual register ID ascending. Available colors come from the eleven-register pool described above, with call-aware preferences.
- **Stack Fallback**: If all available physical registers are occupied by neighbors, the register is allocated to `STACK` residency (falling back to its existing frame value slot).
- **Callee-Saved Preservation**: An 8-byte stack slot is allocated for each physical register used. The prologue saves these registers, and the normal epilogue restores them before `leave` and `ret`.
- **Initialization Semantics**: All reads and writes to physical registers continue to update and check the logical initialization metadata bytes. Residual/stale physical register contents never bypass initialization checks.
- **Default Mode**: `X8664Backend.register_allocation` defaults to `True`. Setting it to `False` explicitly selects the stack-backed diagnostic path.

The S3 1.12 candidate omits native data movement for a `TMOV` only when its
distinct source and destination virtual registers are both proven to have the
same non-stack physical color. It still executes the instruction-budget
instrumentation, checks source initialization when observable, and marks the
destination initialized when required. Different colors and stack endpoints
continue through ordinary load/copy/store lowering.

## Call-aware physical allocation (Milestone 1.22)

Milestone 1.22 extends the allocator without changing the public S3 Assembly.
The full deterministic pool is
`rbx,r12,r13,r14,r15,rdi,rsi,rdx,rcx,r8,r9`; `rsp,rbp,rax,r10,r11` remain
reserved. Values that cross `TCALL` prefer callee-saved registers, while
short-lived values prefer caller-saved registers.

Residency remains whole-function. A logical register is physical or stack
resident for the complete function; there is no interval splitting, general
dynamic spilling, eviction, or frame compaction. Caller-saved values that
survive a call use one backend-only call-spill slot per physical register,
ordered `rdi,rsi,rdx,rcx,r8,r9`, and are saved/restored by the caller around
the call. Callee-saved registers continue to use the function prologue and
epilogue. Logical value slots and initialization metadata remain present and
are not user-visible memory.

Function parameters and outgoing `TCALL` arguments are staged through logical
value slots before ABI registers are overwritten. This intentionally avoids
parallel-copy implementation in this milestone. Snapshot and restore change
physical contents only; initialization validity is still checked on every
logical read and write. Returning helper calls preserve the complete used
caller-saved set conservatively, while noreturn failure helpers need no
artificial restore. Inline syscalls occur only in the external runtime, not in
allocated S3 functions. Register allocation is enabled by default in
`X8664Backend`; benchmark execution is classified separately from correctness.
