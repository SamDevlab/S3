# S3 Benchmarks

Esta infraestrutura realiza benchmarks das APIs e da execução local do S3 no mesmo processo (`in-process`).

## Diferença do Benchmark Exploratório (E0)
A fase exploratória anterior envolvia invocar a CLI externamente, medindo o custo cumulativo do interpretador Python, carregamento do parser e execução do comando. Esta infraestrutura E1 oficial isola os tempos lógicos das APIs executadas (O0/O1) utilizando `time.perf_counter_ns()`, o que garante dados robustos e sem a distorção do startup da CLI. Importante ressaltar que não está sendo testado aqui a geração externa e linker do Assembly x86-64 final (o executável ELF) nem comparando com linguagens como C e Rust (serão abordados nas entregas E3+).

## Modos de Execução
- `hosted-pipeline`: Mede a compilação de fonte para Assembly através das APIs do pacote e a execução no emulador interno (in-process).
- `native-asm-pipeline`: Mede o tempo gasto na transcrição para o Assembly interno e a emissão do S3 Assembly (sem montar um executável).

## Execução
```bash
python tools/benchmark.py --help
python tools/benchmark.py --list
python tools/benchmark.py --mode hosted-pipeline --optimization O1 --workload minimal --warmups 3 --runs 10
```

## Estatísticas
Os tempos reportados (em nanossegundos internamente, e apresentados em milissegundos) englobam: mínimo, máximo, média (`mean`), mediana (`median`) e o percentil 95 (`p95`).
O JSON gerado pela opção `--format json` salva informações sanitizadas e versionadas (Version 1.0.0).

> [!WARNING]
> Resultados de tempo que dependem do hardware da máquina executando a CI **não devem** atuar como barreiras de testes e pipeline, dada a alta variação (`flutuabilidade` nas nuvens).

Para adicionar um workload: crie um arquivo `.s3` e o inclua no array de objetos em `benchmarks/manifest.json`.
