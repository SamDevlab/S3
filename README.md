# S3

[![Tests](https://github.com/SamDevlab/S3/actions/workflows/tests.yml/badge.svg)](https://github.com/SamDevlab/S3/actions/workflows/tests.yml)

S3 é uma linguagem experimental de sistemas baseada em ternário balanceado.
Este repositório contém o bootstrap 0.5 executável:

```text
fonte → frontend → IR verificada → análise de inicialização → O0/O1
      → S3 Assembly 0.5 versionada e validada
      ├→ emulador
      └→ GNU assembly x86-64 → ELF Linux
```

Python está isolado em `bootstrap/`; a fonte normativa é [`spec/`](spec/).

## Marcos 0.3 a 0.5

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
- backend nativo experimental Linux x86-64 para todos os opcodes atuais;
- ELF independente de Python, C, LLVM, libc e runtime padrão;
- System V AMD64, inclusive argumentos adicionais pela pilha;
- entrada explícita de toda função nativa no bloco `entry`;
- limite nativo configurável de 1024 frames por padrão;
- diagnósticos nativos com função, bloco, opcode, origem e valor;
- S3 Assembly `.s3asm 0.5.0` com leitura de legado;
- S3 IR JSON canônica, versionada e verificável;
- análise conservadora de inicialização por CFG;
- níveis O0 (padrão) e O1 local, verificados antes/depois;
- builds preparados para reprodutibilidade na mesma toolchain;
- CI bootstrap em Python 3.11–3.13 e job nativo obrigatório em Ubuntu.

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
python -m bootstrap.s3.cli ir-json examples/static_array.s3 -o build/array.s3ir.json
python -m bootstrap.s3.cli verify-ir build/array.s3ir.json
python -m bootstrap.s3.cli asm examples/static_array.s3
python -m bootstrap.s3.cli asm examples/first.s3 -O1
python -m bootstrap.s3.cli run examples/static_array.s3
python -m bootstrap.s3.cli native-asm examples/first.s3
python -m bootstrap.s3.cli native-asm examples/first.s3 -o build/first.s
python -m bootstrap.s3.cli build examples/first.s3 -o build/first
python -m bootstrap.s3.cli run-native examples/first.s3 -O1 --max-frames 128
```

`ir-json` emite o envelope `s3-ir` 0.5.0 com newline; `verify-ir` reconstrói e
verifica o artefato. `asm` sempre começa por `.s3asm 0.5.0`. `-O0` é padrão;
`-O1` faz somente folding/DCE/threading conservadores. `native-asm` é
determinístico e funciona em qualquer host.
`build`/`run-native` exigem Linux x86-64 e `cc`, `gcc` ou `clang`; o driver usa
somente o assembler/linker com `-nostdlib -no-pie`.

O compilador continua sendo Python. Depois do build, o ELF chama `_start`, usa
syscalls Linux diretamente e imprime:

```text
program returned: 6
program returned: -1
program returned: 0
```

Cada execução imprime uma dessas linhas, conforme o valor decimal assinado
retornado por `main`, sempre seguida por newline.

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
native_abi.s3        → 7
```

O exemplo normativo assembly
[`assembly_recursive_sum.s3asm`](examples/assembly_recursive_sum.s3asm) também
é executado pelos testes e retorna 10.

## Testes e CI

```bash
python -m pytest
```

Saída local registrada no host Windows com Python 3.11.15:

```text
244 passed, 85 skipped
```

Os 85 casos são integrações ELF coletadas e puladas localmente porque este host
não é Linux. O workflow [Tests](.github/workflows/tests.yml), com
`actions/checkout@v6` e `actions/setup-python@v6`, executa a suíte completa em
Ubuntu/Python 3.11–3.13 e um job Linux x86-64 separado com
`S3_NATIVE_REQUIRED=1`; nesse job, toolchain ausente ou skip essencial falha.
Não se afirma aqui que uma execução remota do GitHub já ocorreu.

Uma validação manual adicional montou, ligou e executou GNU assembly com GCC
9.5 em Linux: os onze exemplos produziram os mesmos valores em O0/O1;
overflow, bounds e limite de frames exibiram contexto/valor e status 1.
Identidade byte a byte e `readelf` estão testados no job Linux, mas nenhuma
execução remota do GitHub é alegada antes do push.

## Memória lógica

Objetos possuem tipo, comprimento e mutabilidade. Um `trit` custa 1 trit lógico
e um `tryte`, 6. Cada objeto possui até 365 elementos, o espaço indexável por
`tryte`. Cada frame recebe células próprias inicialmente vazias.

Limites padrão configuráveis:

```text
frames:             1024
instruções:         100000
memória por frame:  6561 trits lógicos (3^8)
```

Índice negativo/fora da faixa, tipo incorreto, leitura não inicializada,
segunda escrita imutável ou excesso de memória terminam com diagnóstico.

Ciclos IR/assembly são permitidos quando estruturalmente válidos. O emulador
limita instruções; emulador e nativo limitam frames S3. O contador nativo é
estado privado do runtime, não memória global da linguagem.

## Backend x86-64

Em objetos físicos, `trit` usa inteiro assinado de 8 bits e `tryte`, inteiro
assinado de 16 bits. Cálculos e slots de registradores virtuais usam 64 bits.
Cada frame contém valores, flags de inicialização, arrays contíguos e um byte
de estado por elemento; o tamanho físico é alinhado a 16 bytes e não se
confunde com a cota lógica.

`TADD` valida overflow, `TBR3` valida -1/0/1, todo acesso valida bounds e
inicialização, e `TMIN`/`TMAX` de trytes usam helpers assembly tritwise. Erros
escrevem em stderr, identificam o ponto lógico e saem com status 1. Contratos:
[representação física](docs/decisions/ADR-0007-x86-64-physical-representation.md),
[ABI/runtime](docs/decisions/ADR-0008-x86-64-native-abi-and-runtime.md) e
[especificação nativa](spec/native-x86_64.md),
[artefatos](spec/artifacts.md), [diagnósticos](spec/native-diagnostics.md) e
[otimização](spec/optimization.md).

## Organização

```text
bootstrap/s3/    frontend, IR, verifier, assembly, emulador e backends
spec/            especificações normativas, incluindo memory.md
docs/decisions/  ADRs 0001–0011
examples/        programas 0.1–0.5 e assembly normativo
tests/           regressão, propriedades e integração
selfhost/        fronteira da futura implementação em S3
```

## Limitações e próximo marco

Não há ponteiros, heap, globals, arrays dinâmicos/multidimensionais, arrays em
assinaturas, strings, estruturas, módulos, I/O, linker próprio, ABI C pública
ou backend para Windows/macOS/ARM64. O target nativo é somente Linux x86-64;
não há interoperabilidade C, JIT, TCO ou otimização interprocedural. ARM64
possui apenas [estudo de viabilidade](docs/arm64-feasibility.md). O próximo
marco recomendado trata diagnósticos estruturados, caching e otimizações
mensuradas; veja o [roadmap](docs/roadmap.md).
