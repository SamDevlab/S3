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

A CLI suporta as versões de sintaxe fonte 0.5 (padrão atual) e 0.6 (preview) através da opção `--source-syntax {0.5,0.6}`.
Exemplos oficiais ainda podem usar a sintaxe 0.5. Consulte o [guia de migração 0.6](docs/migration-source-0.5-to-0.6.md) para detalhes.
A IR JSON e o S3 Assembly continuam na versão 0.5.0, independentemente da sintaxe de origem. O Marco 0.6 ainda não foi concluído.

```bash
python -m bootstrap.s3.cli tokens examples/static_array.s3
python -m bootstrap.s3.cli ast examples/static_array.s3
python -m bootstrap.s3.cli ir examples/static_array.s3
python -m bootstrap.s3.cli ir-json examples/static_array.s3 -o build/array.s3ir.json
python -m bootstrap.s3.cli verify-ir build/array.s3ir.json
python -m bootstrap.s3.cli asm examples/static_array.s3
python -m bootstrap.s3.cli asm examples/first.s3 -O1
python -m bootstrap.s3.cli run examples/static_array.s3
python -m bootstrap.s3.cli run examples/static_array.s3 --diagnostic-format json
python -m bootstrap.s3.cli native-asm examples/first.s3
python -m bootstrap.s3.cli native-asm examples/first.s3 -o build/first.s
python -m bootstrap.s3.cli build examples/first.s3 -o build/first
python -m bootstrap.s3.cli run-native examples/first.s3 -O1 --max-frames 128
```

`ir-json` emite o envelope `s3-ir` 0.5.0 com newline; `verify-ir` reconstrói e
verifica o artefato. `asm` sempre começa por `.s3asm 0.5.0`. `-O0` é padrão;
`-O1` faz somente folding, DCE e threading conservadores. `native-asm` é
determinístico e funciona em qualquer host.

Diagnósticos usam texto em stderr por padrão. Todos os comandos aceitam
`--diagnostic-format json` para emitir um objeto JSON por diagnóstico, no
schema versionado `s3-diagnostic` 1.0.0. Resultados normais permanecem em
stdout. Categorias, códigos, campos opcionais e regras de compatibilidade estão
em [`spec/diagnostics.md`](spec/diagnostics.md).

`--debug` repropaga exceções somente em texto. A combinação com JSON é
rejeitada com um único diagnóstico estruturado e status 2.

O runtime ELF independente continua emitindo os diagnósticos textuais de
`spec/native-diagnostics.md`; a CLI não analisa esse texto para inventar
diagnósticos estruturados.

`build` e `run-native` exigem Linux x86-64 e `cc`, `gcc` ou `clang`; o driver
usa somente o assembler e o linker com `-nostdlib -no-pie`.

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

Os 85 casos são integrações ELF coletadas e puladas localmente porque esse host
não é Linux.

O workflow [Tests](.github/workflows/tests.yml), com
`actions/checkout@v6` e `actions/setup-python@v6`, executa a suíte completa em
Ubuntu com Python 3.11, 3.12 e 3.13, além de um job Linux x86-64 separado com
`S3_NATIVE_REQUIRED=1`.

Nesse job, a ausência da toolchain nativa ou o skip indevido de um teste
obrigatório causa falha.

O Marco 0.5 foi validado remotamente pelo GitHub Actions no commit
[`70d10a0`](https://github.com/SamDevlab/S3/commit/70d10a0), por meio da
execução
[`28712027579`](https://github.com/SamDevlab/S3/actions/runs/28712027579).

Todos os jobs obrigatórios concluíram com sucesso:

- Python 3.11;
- Python 3.12;
- Python 3.13;
- Linux x86-64 nativo.

Na matriz completa de Python, a suíte terminou com 329 testes aprovados em cada
versão. No job nativo Linux x86-64, os 85 testes obrigatórios de integração
foram aprovados.

Uma validação manual adicional montou, ligou e executou GNU assembly com GCC
9.5 em Linux. Os onze exemplos produziram os mesmos valores em O0 e O1;
overflow, bounds e limite de frames exibiram contexto, valor e status 1.

A reprodutibilidade byte a byte dos ELF, os hashes SHA-256 e a inspeção com
`readelf` também são verificadas automaticamente no job Linux.

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

Índice negativo ou fora da faixa, tipo incorreto, leitura não inicializada,
segunda escrita imutável ou excesso de memória terminam com diagnóstico.

Ciclos IR e assembly são permitidos quando estruturalmente válidos. O emulador
limita instruções; emulador e nativo limitam frames S3. O contador nativo é
estado privado do runtime, não memória global da linguagem.

## Backend x86-64

Em objetos físicos, `trit` usa inteiro assinado de 8 bits e `tryte`, inteiro
assinado de 16 bits. Cálculos e slots de registradores virtuais usam 64 bits.

Cada frame contém valores, flags de inicialização, arrays contíguos e um byte
de estado por elemento; o tamanho físico é alinhado a 16 bytes e não se
confunde com a cota lógica.

`TADD` valida overflow, `TBR3` valida `-1`, `0` ou `1`, e todo acesso valida
bounds e inicialização. `TMIN` e `TMAX` de trytes usam helpers assembly
tritwise.

Erros escrevem em stderr, identificam o ponto lógico e encerram com status 1.

Contratos:

- [representação física](docs/decisions/ADR-0007-x86-64-physical-representation.md);
- [ABI e runtime](docs/decisions/ADR-0008-x86-64-native-abi-and-runtime.md);
- [especificação nativa](spec/native-x86_64.md);
- [artefatos](spec/artifacts.md);
- [diagnósticos](spec/native-diagnostics.md);
- [otimização](spec/optimization.md).

## Organização

```text
bootstrap/s3/    frontend, IR, verifier, assembly, emulador e backends
spec/            especificações normativas, incluindo diagnostics.md
docs/decisions/  ADRs 0001–0012
examples/        programas 0.1–0.5 e assembly normativo
tests/           regressão, propriedades e integração
selfhost/        fronteira da futura implementação em S3
```

## Limitações e próximo marco

Não há ponteiros, heap, globals, arrays dinâmicos ou multidimensionais, arrays
em assinaturas, strings, estruturas, módulos, I/O, linker próprio, ABI C
pública ou backend para Windows, macOS ou ARM64.

O target nativo é somente Linux x86-64. Não há interoperabilidade C, JIT, TCO
ou otimização interprocedural. ARM64 possui apenas um
[estudo de viabilidade](docs/arm64-feasibility.md).

O Marco 0.6 foi iniciado pelos diagnósticos estruturados da toolchain
hospedada. Cache e otimizações mensuradas permanecem pendentes; consulte o
[roadmap](docs/roadmap.md).
