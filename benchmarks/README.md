# S3 Benchmarks

Esta infraestrutura realiza benchmarks das APIs e da execução local do S3 no mesmo processo (`in-process`).

## Infraestrutura E1 e E2

A infraestrutura E1 introduziu o runner para separar o custo da CLI, medindo a execução direta das APIs Python. A entrega E2 inseriu métricas determinísticas (contagem de instruções, blocos, funções e opcodes S3 executados) e subdividiu o tempo do pipeline em fases (`PhaseTimer`).

As métricas temporais extraídas **são apenas informativas**. Embora o overhead intrínseco (despacho, setup, teardown) de cada amostra seja calculado separadamente e cada amostra utilize um relógio único (evitando desalinhamento), o tempo medido no ambiente in-process ainda continua sujeito à interferência de:
- CPU scaling;
- Caches de hardware (L1, L2, L3);
- Escalonador de processos (scheduler do SO);
- Ruído térmico e concorrência;
- Garbage Collector do Python (GC).

## Modelo Temporal e Estatísticas

Os tempos reportados englobam mínimo, máximo, média (`mean`), mediana (`median`) e o percentil 95 (`p95`). A saída JSON formatada em `--format json` (schema `benchmark_format_version 1.1.0`) descreve as métricas determinísticas e o registro da versão:
- `checkout_distribution_version`: a versão proveniente do estado atual do git/diretório onde o runner opera;
- `installed_distribution_version`: a versão real da biblioteca s3 instalada (se houver), permitindo comparar a divergência de instâncias.

## Baseline Determinístico

Para atuar como gate de CI (testes automatizados), utilizamos um **baseline determinístico** livre de ruídos temporais e informações de ambiente (OS, arquitetura, timings, CPUs). Para cada configuração O0 e O1, o JSON estrito contém somente:

- retorno esperado;
- contagens de funções, blocos e instruções da IR;
- contagens de funções, blocos e opcodes, tamanho textual e SHA-256 do S3 Assembly;
- opcodes executados, profundidade máxima de frames e chamadas dinâmicas.

O contador `function_call_count` registra apenas as instruções dinâmicas de chamadas `TCALL` (a entrada para a função principal não é computada).

Para regerar o baseline caso haja alterações aprovadas (ex. refatoração semântica no emulador), utilize o comando explícito:
```bash
python tools/generate_deterministic_baseline.py --output benchmarks/baseline-0.8-e2.json
```
Não faça regeração implícita dentro de rodadas normais de benchmark.

## Modos de Execução

- `hosted-pipeline`: Mede a compilação de fonte para Assembly através das APIs do pacote e a execução no emulador interno (in-process).
- `native-asm-pipeline`: Mede o tempo gasto na transcrição para o Assembly interno e a emissão do GNU Assembly x86-64 nativo como string (textual).
**Nota**: O `native-asm-pipeline` não engloba tempos para invocar nenhum assembler, invocar o linker e nem compila/executa o executável ELF resultante.

## Comandos

```bash
python tools/benchmark.py --help
python tools/benchmark.py --list
python tools/benchmark.py --mode hosted-pipeline --optimization both --workload all --warmups 3 --runs 10
```

Quando invocado com `--optimization both`, o runner executa ambas as configurações (O0 e O1) e emite uma comparação neutra com razões informativas de proporção temporal e volumétrica (crescimento ou decréscimo estrutural).

Para adicionar um novo workload: crie um arquivo `.s3` em `benchmarks/` e registre-o com o respectivo id e constraints no array dentro de `benchmarks/manifest.json`.

## s3bench 1.0

Milestones 1.17-1.19 add a new protocol beside the historical 0.8 runner. The
old `tools/benchmark.py`, `manifest.json`, and `baseline-0.8-e2.json` remain
unchanged historical and deterministic infrastructure.

The new entry point is:

```bash
python tools/s3bench.py --list
python tools/s3bench.py --dry-run
python tools/s3bench.py --verify-only --output-json benchmarks/results/verify.json
python tools/s3bench.py --smoke --output-json benchmarks/results/smoke.json
```

## Repeatability analyzer

The official repeatability analyzer consumes persisted `s3bench` runs without
executing benchmarks. It validates the result/comparison join contract,
checksums, stderr, stdout parity, complete run sets, and measurement scope.

```bash
python tools/s3bench_analyze.py ROOT \
  --output-json report.json \
  --output-markdown report.md \
  --expected-runs 3
```

`ROOT` may contain `benchmarks/<benchmark-safe-id>/run-1/` directly, or a
`benchmarks/` child directory. Each run contains `results.json` and may
contain `results.stdout` and `results.stderr`:

```text
ROOT/
  benchmarks/
    <benchmark-safe-id>/
      benchmark-id.txt
      run-1/results.json
      run-1/results.stdout
      run-1/results.stderr
      run-2/...
      run-3/...
```

`benchmark-id.txt` contains the canonical `benchmark_id`. The directory name
is only a safe storage name and is never used as the benchmark identity. If
the marker is absent, the analyzer derives the ID from the documents and
requires it to remain identical across all runs.

Report publication is transactional until both output files are installed.
Pre-commit failures restore previous destinations. If restoration itself
fails, the original backup is preserved and the error identifies its path for
manual recovery; a backup containing original data is never silently removed.

## Optimization budgets

Versioned structural budgets for selected examples are checked with:

```bash
python tools/check_optimization_budgets.py
```

The manifest at `benchmarks/optimization-budgets.json` limits O1 block,
instruction, and branch counts and can reject structural growth. These are
deterministic compatibility budgets, not timing thresholds or performance
claims.

Kernel measurements are analyzed in nanoseconds per loop:
`median_ns / loops_per_sample`, verified against
`comparison.median_ns_per_loop`. The raw `median_ns` is the total sample
time and must never be used directly to compare kernel results. Process
measurements require `loops_per_sample == 1`; their canonical unit is also
`median_ns_per_loop`, representing complete process time per sample.
Kernel and process scopes are never compared directly.

Across runs, `STABLE` means amplitude and median CV are both at most 10%,
`USABLE` means both are at most 20%, and all other results are `UNSTABLE`.
S3 emulator O1 versus O0 is `CONCLUSIVE` only when neither side is unstable
and the absolute change exceeds the larger observed amplitude. Otherwise it
is `INCONCLUSIVE`; inconclusive changes must not be described as regressions.

The versioned manifest is `manifests/s3bench-1.0.0.json`; the result schema is
`schema/s3bench-1.0.0.schema.json`. Local machine-specific files under
`benchmarks/results/` and build artifacts under `benchmarks/build/` are ignored.

The harness always discovers and builds before verification. Verification must
produce exactly one `checksum=<value>` line (or the equivalent internal S3
result) matching the manifest. Only then may warmup, bounded calibration, and
measurement proceed. `time.perf_counter_ns()` supplies durations. Raw measured
samples are preserved; warmup and calibration observations are excluded.

JSON contains separate compile, link, startup, kernel, process/end-to-end,
artifact-size, and optional peak-memory fields. An unsupported phase is `null`,
never zero. Results omit usernames, private hostnames, personal paths,
environment dumps, network identifiers, credentials, and tokens.

Shared CI smoke checks functionality and determinism without a performance
threshold. Reviewed native baselines require one controlled Linux environment.
Smoke output is never authoritative performance data.
