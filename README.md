# S3

S3 é uma linguagem de sistemas experimental baseada em lógica ternária
balanceada. O repositório contém um bootstrap executável e testável:

```text
fonte S3 → lexer → AST → semântica → S3 IR verificada
         → S3 Assembly textual → emulador → resultado
```

Python está isolado em `bootstrap/` como implementação de referência
temporária. O núcleo futuro escrito em S3 permanece separado em `selfhost/`.
A fonte normativa é [`spec/`](spec/).

## Estado atual — Marco 0.2

O S3 suporta:

- `trit` (`-1`, `0`, `1`) e `tryte` (`-364` a `364`);
- funções sem sobrecarga, parâmetros tipados e múltiplas funções por arquivo;
- chamadas como expressões, chamadas aninhadas, forward calls e recursão;
- variáveis locais imutáveis e escopos independentes nos casos;
- `return` com análise de todos os caminhos;
- `switch` ternário exaustivo, sem `default` ou fallthrough;
- operadores `~`, `-` unário, `+`, `-`, `&`, `|` e `<=>`;
- IR tipada com blocos básicos e verificador estrutural separado;
- assembly tipada com parâmetros, registradores, labels, chamadas e saltos;
- emulador com pilha explícita de frames e limites de segurança;
- metadados de linha/coluna preservados até as instruções.

Subtração existe apenas na fonte e AST. O lowering sempre produz inversão
seguida de soma; não existe `SUBTRACT` na IR nem `TSUB` na assembly.

## Instalação

Requer Python 3.11 ou mais recente. O runtime usa somente a biblioteca padrão;
`pytest` é dependência de desenvolvimento.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# PowerShell:
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Também é possível executar diretamente da raiz:

```bash
python -m bootstrap.s3.cli run examples/recursive_sum.s3
```

## CLI

Todos os comandos existentes foram preservados:

```bash
python -m bootstrap.s3.cli tokens examples/first.s3
python -m bootstrap.s3.cli ast examples/first.s3
python -m bootstrap.s3.cli ir examples/recursive_sum.s3
python -m bootstrap.s3.cli asm examples/recursive_sum.s3
python -m bootstrap.s3.cli run examples/recursive_sum.s3
```

Após instalação editável, `s3` é um atalho equivalente.

Exemplos:

```bash
python -m bootstrap.s3.cli run examples/first.s3
# program returned: 6

python -m bootstrap.s3.cli run examples/simple_call.s3
# program returned: 15

python -m bootstrap.s3.cli run examples/nested_calls.s3
# program returned: 12

python -m bootstrap.s3.cli run examples/sign.s3
# program returned: -1

python -m bootstrap.s3.cli run examples/recursive_sum.s3
# program returned: 10
```

## Testes

```bash
python -m pytest
```

Saída completa registrada em Python 3.11.15:

```text
........................................................................ [ 75%]
........................                                                 [100%]
96 passed in 2.38s
```

A suíte cobre o modelo ternário, regressões 0.1, parser, resolução em duas
fases, escopos, análise de retorno, lowering, verificador da IR, round-trip da
assembly, três vias de controle, frames, recursão, limites e diagnósticos.

## Organização

```text
S3/
├── bootstrap/s3/
│   ├── lexer.py, parser.py, ast.py
│   ├── semantic.py
│   ├── ir.py, lowering.py, verifier.py
│   ├── assembly.py, codegen.py
│   ├── emulator.py, pipeline.py, cli.py
│   └── ternary.py, diagnostics.py
├── docs/
│   ├── decisions/
│   ├── architecture.md
│   └── roadmap.md
├── examples/
│   ├── first.s3
│   ├── simple_call.s3
│   ├── nested_calls.s3
│   ├── sign.s3
│   └── recursive_sum.s3
├── selfhost/
├── spec/
└── tests/
```

## ABI lógica e limites

Cada chamada cria um frame com registradores próprios. Argumentos são copiados
por valor para `.param` na ordem declarada. `TRET` copia o resultado ao
registrador de destino do chamador e restaura bloco/posição lógicos.

Os limites padrão são 1024 frames simultâneos e 100.000 instruções por execução.
São configuráveis na API `Emulator`; excedê-los produz erro e nunca altera
silenciosamente um resultado.

## Limitações

Ainda não existem memória endereçável, ponteiros, arrays, estruturas,
atribuição posterior, loops próprios, módulos, imports, funções externas, I/O,
linker, backend nativo, `PHI` ou autohospedagem. Recursão é o mecanismo atual de
repetição. A ABI é lógica e não representa uma ABI física x86-64/ARM64.

O próximo marco é o 0.3: memória e agregados mínimos. Consulte o
[roadmap](docs/roadmap.md).
