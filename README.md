# S3

[![Tests](https://github.com/SamDevlab/S3/actions/workflows/tests.yml/badge.svg)](https://github.com/SamDevlab/S3/actions/workflows/tests.yml)

S3 é uma linguagem experimental de sistemas baseada em **ternário balanceado**, com foco em semântica explícita, execução determinística, segurança de memória por construção e um caminho nativo Linux x86-64 verificável.

O pacote publicável continua sendo **`s3-bootstrap` 0.7.0**. A linha interna **1.x** evolui o compilador, a linguagem e o runtime sem implicar automaticamente um novo release público.

```text
fonte S3
  ↓
lexer / parser / semântica
  ↓
IR tipada e verificada
  ↓
O0 / O1 + verificação
  ↓
S3 Assembly versionada
  ├─→ emulador
  └─→ backend Linux x86-64 → ELF nativo
```

O compilador de referência continua em Python dentro de `bootstrap/`. Os programas nativos gerados não dependem de Python para executar.

## Estado atual

A linha atual já vai além do MVP 0.7 e inclui, entre outras capacidades:

- `trit` e `tryte` balanceados, preservando a semântica ternária original;
- `i64` assinado de 64 bits com aritmética checked;
- `f64` IEEE-754 binary64;
- funções, chamadas, recursão, `while`, `for`, `break`, `continue` e `match`;
- bindings imutáveis e `mut` explícito;
- arrays estáticos e bounds checking;
- records e enums nominais;
- módulos determinísticos com imports/exports explícitos;
- referências seguras `&T` e `&mut T`, sem raw pointers;
- referências para elementos de arrays e campos de records;
- reborrow de referências;
- IR SSA/CFG, verificação, emulação e backend nativo;
- O0 e O1 com contratos de correção;
- backend Linux x86-64 com System V AMD64;
- CI em Python 3.11–3.13, gates diferenciais, SSA, benchmark e Linux nativo obrigatório.

A versão publicável permanece 0.7.0 enquanto essas milestones internas amadurecem.

## Domínios numéricos

### `trit` e `tryte`

Os tipos balanceados continuam sendo parte central da linguagem. A introdução de tipos de máquina não redefine operadores ternários nem transforma valores inteiros em ponteiros.

### `i64`

`i64` é um inteiro assinado de 64 bits com operações checked:

```text
+
-
*
/
unary -
== != < <= > >=
```

Overflow não faz wrap silencioso. Divisão por zero e o caso `INT64_MIN / -1` são tratados como falhas determinísticas.

A subtração de máquina possui uma operação tipada própria no pipeline (`NUMERIC_DIFFERENCE` / `TNDIFF`) para que casos válidos como:

```text
INT64_MIN - INT64_MIN == 0
-1 - INT64_MIN == INT64_MAX
```

não sofram um overflow intermediário artificial causado por uma transformação `negate + add`.

A subtração balanceada de `trit`/`tryte` continua usando o lowering histórico `INVERT + ADD`; não existe um opcode genérico `SUBTRACT`/`TSUB` para substituir essa semântica.

### `f64`

`f64` segue IEEE-754 binary64 e oferece:

```text
+
-
*
/
unary -
== != < <= > >=
```

NaN, `+Inf`, `-Inf` e signed zero permanecem valores válidos. O compilador não habilita fast-math nem reassociação que altere a semântica IEEE-754.

No backend Linux x86-64, operações `f64` usam SSE2/XMM e o ABI interno suporta argumentos inteiros e floating-point no mesmo fluxo System V AMD64.

### Conversões explícitas

As conversões numéricas iniciais são explícitas:

```text
to_i64(trit|tryte) -> i64
to_f64(trit|tryte|i64) -> f64
to_tryte(i64) -> tryte
```

`to_tryte(i64)` é checked para a faixa balanceada `[-364, 364]`.

Não existem casts entre referências e inteiros.

## Exemplo numérico

```s3
fn score(logp: f64, mw: f64, aromatic: f64, tpsa: f64) -> f64:
    return -3.0 + logp * -0.35 + (mw / 100.0) * -0.2 + aromatic * -0.4 + (tpsa / 50.0) * 0.15

fn main() -> trit:
    mut counter: i64 = 0
    while counter < 1000000:
        counter = counter + 1

    return (counter == 1000000) & (score(2.0, 300.0, 2.0, 50.0) < -4.54)
```

A milestone numérica possui probes end-to-end para parser, semântica, IR, Assembly, emuladores e backend Linux x86-64, incluindo um loop nativo cujo contador `i64` chega a 1.000.000.

## Referências seguras

S3 possui referências tipadas seguras:

```text
&T
&mut T
```

O modelo atual evita:

- null references;
- raw pointers;
- pointer arithmetic;
- casts referência ↔ inteiro;
- comparação de identidade de ponteiros como semântica pública.

`&mut` representa capacidade de escrita. Ele não deve ser interpretado automaticamente como o mesmo modelo de exclusividade/noalias de Rust.

A implementação atual suporta referências a storage local, elementos de arrays, campos de records e reborrow, com proveniência preservada pelo compilador.

## Pipeline do compilador

O fluxo principal é:

```text
source
  → lexer
  → parser
  → semantic analysis
  → typed IR
  → verifier
  → optimization
  → S3 Assembly
  → Assembly verifier
  ├→ Assembly emulator
  └→ Linux x86-64 backend
```

A infraestrutura inclui:

- CFG e dominância;
- SSA e verificação por passes;
- constant propagation/folding;
- DCE e otimizações conservadoras;
- Memory Effects/proveniência para referências;
- differential testing;
- contratos determinísticos de serialização e Assembly;
- register allocation GPR experimental no backend nativo.

Otimização nunca deve alterar a semântica observável do programa.

## Backend nativo

O target nativo principal é **Linux x86-64**.

O backend gera GNU assembly e usa a toolchain disponível (`cc`, `gcc` ou `clang`) para montar e linkar o ELF.

```bash
s3 native-asm examples/first.s3 -o build/first.s
s3 build examples/first.s3 -o build/first
s3 run-native examples/first.s3
```

O caminho nativo continua sendo obrigatório mesmo com a evolução futura de containers e providers externos.

## Instalação

```bash
python -m venv .venv
```

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Instalação:

```bash
python -m pip install .
s3 --help
s3 run examples/first.s3
```

Para desenvolvimento:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

O pacote não possui dependências runtime externas obrigatórias; `pytest` e `pytest-xdist` pertencem ao ambiente de desenvolvimento.

## CLI

A sintaxe fonte V0.6 continua sendo o modo padrão da versão publicável.

Comandos comuns:

```bash
s3 targets
s3 doctor
s3 check examples/first.s3
s3 inspect examples/first.s3
s3 inspect examples/first.s3 --emit ir
s3 inspect examples/first.s3 --emit assembly
s3 tokens examples/static_array.s3
s3 ast examples/static_array.s3
s3 ir examples/static_array.s3
s3 ir-json examples/static_array.s3 -o build/array.s3ir.json
s3 verify-ir build/array.s3ir.json
s3 asm examples/first.s3 -O1
s3 run examples/static_array.s3
s3 native-asm examples/first.s3 -o build/first.s
s3 build examples/first.s3 -o build/first
s3 run-native examples/first.s3 -O1
```

Em um checkout sem instalação:

```bash
python -m bootstrap.s3.cli --help
```

A sintaxe V0.5 permanece apenas como compatibilidade legada/deprecated por seleção explícita.

## Testes e CI

A suíte possui categorias explícitas para separar correção rápida, contratos, diferencial, nativo, testes lentos e benchmarks:

```text
s3_fast
s3_contract
s3_differential
s3_native
s3_slow
s3_benchmark
```

Execução local:

```bash
python -m pytest
python tools/golden_inspect.py check
```

O workflow principal cobre Python 3.11, 3.12 e 3.13, além de gates separados para:

- Linux x86-64 nativo;
- verificação SSA por passes;
- diferencial determinístico;
- renderer/goldens;
- benchmark smoke;
- capability probes específicos quando uma milestone exige evidência end-to-end.

Benchmarks são caracterização. Correção, equivalência, checksums e contratos semânticos são gates de correctness.

## Renderer e self-hosting

O projeto contém uma linha incremental de self-hosting e renderer Assembly escrita em S3.

Python continua sendo o compilador de referência e o caminho padrão. Componentes em S3 só substituem o caminho Python quando equivalência, cobertura e gates próprios demonstrarem que a migração é segura.

A estratégia é progressiva: primeiro construir componentes verificáveis, depois comparar contra a implementação de referência e somente então promover o caminho S3.

## Roadmap de capacidades

A ordem arquitetural atual da linha de produção é:

```text
NUMERIC
  ↓
SLICES
  ↓
FFI
  ↓
DYNAMIC
  ↓
HOST_SERVICES
  ↓
PROJECT_CONTAINER_MODEL
  ↓
S3_DOCKER
```

Correspondência das milestones:

```text
1.32  Numeric Domains & Large Indexing
1.33  Borrowed Slices & Large Contiguous Buffers
1.34  Foreign ABI, Library Mode & Zero-Copy Host Interop
1.35  Owned Dynamic Runtime Data
1.36  Linux Host Services & Foreign Tool Interop
1.37  S3 Project & Container-Native Application Model
1.38  S3 Docker V1
```

A existência de código, documentação ou uma PR numerada não é, sozinha, prova de conclusão de uma capacidade. Cada milestone precisa demonstrar a funcionalidade prometida de forma utilizável por um programador S3 e passar seus gates end-to-end antes de ser considerada completa.

O princípio estratégico é **external-first quando isso for mais eficiente**: bibliotecas C, Linux, Python, Docker/OCI e outros componentes maduros podem atuar como providers enquanto o núcleo S3 amadurece. Reimplementações nativas só devem substituir esses providers quando houver motivo concreto de desempenho, controle, segurança ou self-hosting.

## Interoperabilidade

S3 não pretende existir isolado do ecossistema.

A direção arquitetural inclui:

- C ABI como lingua franca de interoperabilidade;
- bibliotecas S3 carregáveis por hosts externos;
- buffers contíguos e zero-copy;
- integração com Python/C/C++/Rust por camadas de ABI;
- processos, argv/env, stdin/stdout/stderr, arquivos e pipes;
- Docker/OCI como sistema de compatibilidade e aplicação;
- GPU inicialmente por integração com engines existentes, antes de um backend GPU próprio.

Nem todas essas capacidades fazem parte da versão publicável 0.7.0; elas pertencem à evolução interna 1.x e exigem gates próprios antes de promoção.

## Limitações atuais

S3 ainda não é uma linguagem de produção geral e mantém limites deliberados.

Entre eles:

- sem raw pointers, null ou pointer arithmetic;
- sem garbage collector;
- sem generics gerais;
- sem concorrência de linguagem madura;
- sem backend nativo completo para Windows, macOS ou ARM64;
- sem JIT ou otimização interprocedural madura;
- self-hosting ainda incremental;
- capacidades de slices, FFI, runtime dinâmico, serviços de host e containers só devem ser tratadas como públicas quando seus respectivos gates de capability estiverem concluídos.

O target nativo de referência permanece Linux x86-64.

## Organização do repositório

```text
bootstrap/s3/    frontend, IR, verifier, Assembly, emuladores e backends
spec/            especificações e contratos normativos
docs/            milestones, decisões arquiteturais e documentação técnica
docs/decisions/  ADRs
examples/        programas S3 e fixtures oficiais
tests/           regressão, contratos, diferencial, nativo e benchmarks
selfhost/        fronteira da evolução Python → S3
```

## Documentação

Pontos de entrada úteis:

- [`docs/roadmap.md`](docs/roadmap.md) — roadmap geral;
- [`docs/milestone-1.32.md`](docs/milestone-1.32.md) — Numeric Domains & Large Indexing;
- [`spec/`](spec/) — especificações normativas;
- [`docs/decisions/`](docs/decisions/) — decisões arquiteturais;
- [`docs/releases/0.7.0.md`](docs/releases/0.7.0.md) — release público 0.7.0.

## Licença

Apache-2.0.
