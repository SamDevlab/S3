# S3

[![Tests](https://github.com/SamDevlab/S3/actions/workflows/tests.yml/badge.svg)](https://github.com/SamDevlab/S3/actions/workflows/tests.yml)

S3 é uma linguagem experimental de sistemas baseada em ternário balanceado.
Este repositório contém o bootstrap 0.3 executável:

```text
fonte → frontend → IR verificada → S3 Assembly → emulador
```

Python está isolado em `bootstrap/`; a fonte normativa é [`spec/`](spec/).

## Marco 0.3

Suporte atual:

- `trit` e `tryte`, overflow detectável e sem unsigned;
- funções, chamadas, recursão e switch ternário exaustivo;
- bindings imutáveis e `mut` explícito;
- atribuição escalar e indexada;
- arrays estáticos unidimensionais de `trit`/`tryte`;
- bounds estático para índices constantes e dinâmico para calculados;
- objetos de memória locais ao frame, sem ponteiros ou aliasing;
- IR SSA com CFG, dominância, `LOAD` e `STORE`;
- assembly com `.memory`, `TLOAD` e `TSTORE`;
- leitura não inicializada sempre diagnosticada;
- CI em Python 3.11, 3.12 e 3.13.

Não existem `PHI`, `SUBTRACT`, `TSUB`, heap ou memória global.

## Instalação

```bash
python -m venv .venv
# PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

O runtime usa somente a biblioteca padrão. `pytest` é dependência de
desenvolvimento.

## CLI

```bash
python -m bootstrap.s3.cli tokens examples/static_array.s3
python -m bootstrap.s3.cli ast examples/static_array.s3
python -m bootstrap.s3.cli ir examples/static_array.s3
python -m bootstrap.s3.cli asm examples/static_array.s3
python -m bootstrap.s3.cli run examples/static_array.s3
```

`ir` exibe `memory_objects`, `load` e `store`; `asm` exibe `.memory`, `TLOAD` e
`TSTORE`.

Resultados dos exemplos:

```text
first.s3             → 6
simple_call.s3       → 15
nested_calls.s3      → 12
sign.s3              → -1
recursive_sum.s3     → 10
mutable_value.s3     → 15
mutable_switch.s3    → 10
static_array.s3      → 13
trit_array.s3        → 1
recursive_memory.s3  → 6
```

O exemplo normativo assembly
[`assembly_recursive_sum.s3asm`](examples/assembly_recursive_sum.s3asm) também
é executado pelos testes e retorna 10.

## Testes e CI

```bash
python -m pytest
```

Saída local registrada com Python 3.11.15:

```text
........................................................................ [ 41%]
........................................................................ [ 82%]
...............................                                          [100%]
175 passed in 3.34s
```

O workflow [Tests](.github/workflows/tests.yml) executa instalação editável e a
suíte completa em Ubuntu com Python 3.11–3.13, em `push` e `pull_request`, sem
`continue-on-error`.

## Memória lógica

Objetos possuem tipo, comprimento e mutabilidade. Um `trit` custa 1 trit lógico
e um `tryte`, 6. Cada objeto possui até 365 elementos, o espaço indexável por
`tryte`. Cada frame recebe células próprias inicialmente vazias.

Limites padrão configuráveis:

```text
frames:             1024
instruções:         100000
memória por frame:  2187 trits lógicos
```

Índice negativo/fora da faixa, tipo incorreto, leitura não inicializada,
segunda escrita imutável ou excesso de memória terminam com diagnóstico.

Ciclos IR/assembly são permitidos quando estruturalmente válidos; execução sem
retorno é interrompida pelo limite de instruções.

## Organização

```text
bootstrap/s3/    frontend, IR, verifier, assembly e emulador
spec/            especificações normativas, incluindo memory.md
docs/decisions/  ADRs 0001–0006
examples/        programas 0.1–0.3 e assembly normativo
tests/           regressão, propriedades e integração
selfhost/        fronteira da futura implementação em S3
```

## Limitações e próximo marco

Não há ponteiros, heap, globals, arrays dinâmicos/multidimensionais, arrays em
assinaturas, strings, estruturas, módulos, I/O, linker, ABI física ou backend
nativo. O Marco 0.4 recomendado prepara layout físico e um backend x86-64
mínimo; veja o [roadmap](docs/roadmap.md).
