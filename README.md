# S3

[![Tests](https://github.com/SamDevlab/S3/actions/workflows/tests.yml/badge.svg)](https://github.com/SamDevlab/S3/actions/workflows/tests.yml)

S3 é uma linguagem experimental de sistemas baseada em ternário balanceado.
Este repositório contém a versão publicável
`s3-bootstrap` 0.7.0, com sintaxe fonte V0.6 por padrão e formatos IR JSON e
S3 Assembly 0.5.0:

```text
fonte → frontend → IR verificada → análise de inicialização → O0/O1
      → S3 Assembly 0.5 versionada e validada
      ├→ emulador
      └→ GNU assembly x86-64 → ELF Linux
```

Python está isolado em `bootstrap/`; a fonte normativa é [`spec/`](spec/).

## Suporte atual

A implementação atual oferece:

- `trit` e `tryte`, overflow detectável e sem unsigned;
- funções, chamadas, recursão e `match` ternário exaustivo no default V0.6;
- `switch` ternário exaustivo somente no modo V0.5 explícito;
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
- limite hospedado e nativo configurável de 100000 instruções por padrão;
- faixa nativa u64 isolada por processo;
- limite nativo configurável de 1024 frames por padrão;
- diagnósticos nativos com função, bloco, opcode, origem e valor;
- S3 Assembly `.s3asm 0.5.0` com leitura de legado;
- S3 IR JSON canônica, versionada e verificável;
- análise conservadora de inicialização por CFG;
- níveis O0 (padrão) e O1 local, verificados antes/depois;
- builds preparados para reprodutibilidade na mesma toolchain;
- CI bootstrap em Python 3.11–3.13 e job nativo obrigatório em Ubuntu.

Não existem `PHI`, `SUBTRACT`, `TSUB`, heap ou memória global.

## Contrato do Marco 0.7

A versão 0.7.0 inclui fonte V0.6 por padrão e V0.5 por seleção
explícita; `trit`, `tryte`, funções, chamadas, recursão, mutabilidade,
`match`, arrays estáticos e acesso indexado; bounds e análise de inicialização;
IR verificada, O0/O1, S3 Assembly e emulador; backend experimental Linux
x86-64 com ELF independente de Python depois do build; limite de instruções
hospedado e nativo compartilhado (default 100000); limite de frames nativo;
diagnósticos em texto e JSON; CLI pública; e suporte a Python 3.11, 3.12 e 3.13.

Ficam fora deste MVP: ponteiros, heap, memória global, structs, strings,
módulos, I/O da linguagem, package manager, LSP, depurador, generics, macros,
concorrência, ARM64, backends Windows/macOS, self-hosting, ABI C pública e
arrays dinâmicos ou multidimensionais. Esses limites definem o escopo do MVP;
não são pendências da Entrega E.

## Instalação

```bash
python -m venv .venv

# PowerShell:
.venv\Scripts\Activate.ps1

# Linux/macOS:
source .venv/bin/activate

python -m pip install .
s3 --help
s3 run examples/first.s3
```

Para desenvolvimento:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

O runtime usa somente a biblioteca padrão. `pytest` é dependência de
desenvolvimento.

## CLI

A CLI usa a sintaxe fonte 0.6 por padrão. Os exemplos oficiais já usam V0.6,
portanto os comandos comuns não precisam de uma opção de versão. A sintaxe
V0.5 permanece temporariamente disponível com `--source-syntax 0.5`. Não há
autodetecção, fallback ou migração automática; consulte o
[guia de migração 0.6](docs/migration-source-0.5-to-0.6.md).

A versão da fonte é independente dos artefatos: IR JSON e S3 Assembly
continuam em 0.5.0. O Marco 0.7 está concluído.

```bash
s3 targets
s3 doctor
s3 check examples/first.s3
s3 inspect examples/first.s3
s3 inspect examples/first.s3 --emit summary
s3 inspect examples/first.s3 --emit ir
s3 inspect examples/first.s3 --emit assembly
s3 tokens examples/static_array.s3
s3 ast examples/static_array.s3
s3 ir examples/static_array.s3
s3 ir-json examples/static_array.s3 -o build/array.s3ir.json
s3 verify-ir build/array.s3ir.json
s3 asm examples/static_array.s3
s3 asm examples/first.s3 -O1
s3 run examples/static_array.s3 --max-instructions 200000
s3 run examples/static_array.s3 --diagnostic-format json
s3 native-asm examples/first.s3 --max-instructions 200000
s3 native-asm examples/first.s3 -o build/first.s
s3 build examples/first.s3 -o build/first --max-instructions 200000
s3 run-native examples/first.s3 -O1 --max-frames 128 --max-instructions 200000
s3 --source-syntax 0.5 run legacy-v0.5.s3
```

Em um checkout sem instalação, a forma equivalente é
`python -m bootstrap.s3.cli`.

`targets` mostra os targets e providers internos disponíveis. `doctor`
diagnostica Python, host, targets, execução hospedada, assembly nativo e a
disponibilidade da `NativeToolchain`.

`check` valida se um arquivo fonte compila, sem executar o programa, sem gerar
ELF e sem chamar o backend nativo. `inspect` mostra um resumo da compilação por
padrão; `--emit summary` torna esse modo explícito. `--emit ir` emite o IR JSON
do compilador atual, e `--emit assembly` emite o S3 Assembly atual para
inspection e comparação.

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
python tools/golden_inspect.py check
python tools/golden_inspect.py update
```

`tools/golden_inspect.py check` compara os golden artifacts versionados em
`tests/golden/inspect/` com a saída atual do compilador. `update` regenera esses
goldens quando uma mudança de IR ou S3 Assembly for intencional. A cobertura
atual inclui `examples/first.s3`, `examples/simple_call.s3`,
`examples/sign.s3` e `examples/self_hosting/assembly_renderer_stub.s3`; essa
infraestrutura serve como ponto de comparação para a future Python-to-S3
migration, não como benchmark.

No caminho do renderer candidato, S3 0.15 está fechado e S3 0.16 também está
fechado após generalizar incrementalmente o renderer core para os três probes
atuais. `first`, `simple_call` e `sign` têm actual outputs disponíveis,
`comparison_status: passed`, e agora passam por um renderer core Python mínimo
baseado em `StaticTextLineEmitter`. S3 0.17 está fechado após aproximar o
modelo real `AssemblyProgram` desse core por adapters controlados; `first`,
`simple_call` e `sign` são provados byte a byte via adapter.
S3 0.18 está fechado após consolidar esses adapters atrás de
`render_supported_program`, um caminho comum para o subconjunto
`AssemblyProgram` já provado por `first`, `simple_call` e `sign`, sem alterar
outputs versionados ou goldens. S3 0.19 está fechado após expandir esse caminho
Python-side para cobrir a saída atual de `AssemblyProgram.render()` e fazer
`AssemblyProgram.render()` delegar a ele. Isso preserva os inspect goldens e os
actual outputs; o renderer S3 real continua não implementado. S3 0.20 está
fechado após adicionar
`examples/self_hosting/assembly_renderer_bootstrap.s3`, um spike S3 executável
que valida invariantes escalares do subset suportado sem emitir texto Assembly
completo.
`python tools/compare_assembly_renderer.py --candidate-compare-available` é o
modo correto para validar esses outputs disponíveis.
`python tools/compare_assembly_renderer.py --candidate-run` também valida o
spike e reporta que renderer implementation/full text rendering continuam
`not_implemented`.
`python tools/compare_assembly_renderer.py --check` continua bloqueado com
status 1 porque o renderer S3 real ainda não está implementado; isso evita
falso positivo de sucesso global.

Integrações ELF são coletadas e puladas em hosts que não são Linux. Os
resultados atuais devem ser consultados no workflow; os números abaixo
documentam especificamente a validação histórica do Marco 0.5.

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

Na matriz histórica do Marco 0.5, a suíte terminou com 329 testes aprovados em
cada versão. No job nativo Linux x86-64, os 85 testes obrigatórios de
integração foram aprovados.

Uma validação manual adicional montou, ligou e executou GNU assembly com GCC
9.5 em Linux. Os onze exemplos produziram os mesmos valores em O0 e O1;
overflow, bounds e limite de frames exibiram contexto, valor e status 1.

A reprodutibilidade byte a byte dos ELF, os hashes SHA-256 e a inspeção com
`readelf` também são verificadas automaticamente no job Linux.

A Entrega D2B foi validada no
[run 28726929769](https://github.com/SamDevlab/S3/actions/runs/28726929769):
os jobs Python 3.11–3.13 e Linux x86-64 nativo concluíram com sucesso.

A preparação final da Entrega E, commit
[`aceee82`](https://github.com/SamDevlab/S3/commit/aceee820ebc99b7d90fc5d32dd8fa8e699ad37b5),
foi validada no
[run 28737520765](https://github.com/SamDevlab/S3/actions/runs/28737520765),
com 561 testes em cada versão de Python e 85 integrações nativas obrigatórias.

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
limita instruções e o backend nativo impõe o mesmo limite no ELF, respeitando
o teto u64 de `1` a `2**64 - 1` na CPU. Emulador e nativo limitam frames S3.
O contador nativo é estado privado do runtime, não memória global da linguagem.

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
docs/decisions/  ADRs 0001–0013
docs/releases/   notas de lançamento
examples/        programas oficiais V0.6 e assembly normativo
tests/           regressão, propriedades e integração
selfhost/        fronteira da futura implementação em S3
```

## Limitações e próximo marco

Não há ponteiros, heap, globals, arrays dinâmicos ou multidimensionais, arrays
em assinaturas, strings, estruturas, módulos, I/O, package manager, LSP,
depurador, generics, macros, concorrência, linker próprio, ABI C pública,
self-hosting ou backend para Windows, macOS ou ARM64.

O target nativo é somente Linux x86-64. Não há interoperabilidade C, JIT, TCO
ou otimização interprocedural. ARM64 possui apenas um
[estudo de viabilidade](docs/arm64-feasibility.md).

O Marco 0.7 está concluído e a versão 0.7.0 está publicada. O desenvolvimento
encontra-se estruturando normativamente a medição de desempenho do
[Marco 0.8](docs/milestone-0.8.md) (trabalho em andamento).
Os demais recursos classificados como Pós-MVP continuam não implementados. Consulte
o [roadmap](docs/roadmap.md) e as
[notas de lançamento](docs/releases/0.7.0.md).
