# S3 Benchmarks

Esta infraestrutura realiza benchmarks das APIs e da execução local do S3 no mesmo processo (`in-process`).

## Infraestrutura E1 e E2 integradas

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

## Fundação interna da E3

A implementação da E3 continua parcial, mas já possui a fundação interna do
ciclo de vida de um ELF e o loop validado de amostragem. O módulo
`tools/benchmark_native.py` separa solicitação de build, artefato nativo,
execução direta, validação funcional e coleta de amostras. O builder usa o
comando público de build já existente, enquanto o executor recebe um artefato
pronto e não conhece fonte S3 ou toolchain. O validador consome apenas o
resultado bruto e não acessa processos ou filesystem.

As estatísticas temporais foram isoladas no módulo puro
`tools/benchmark_statistics.py`, sem subprocessos, filesystem, relógio, CLI ou
backend. Ele centraliza minimum, maximum, mean, median e p95, preservando o
cálculo nearest-rank para p95 e recebendo apenas amostras já validadas em
nanossegundos.

As superfícies públicas planejadas continuam separadas:

- `cli-end-to-end`: medição da experiência completa de um comando público já
  existente, incluindo os custos reais atravessados por esse comando;
- `elf-execution`: medição exclusiva de um ELF Linux x86-64 previamente
  construído e validado, sem incluir build ou inicialização da CLI na amostra.

Para a execução isolada, cada combinação de workload e O0/O1 constrói o ELF
uma única vez antes do loop interno. O mesmo artefato passa por preflight
funcional, warmups validados e descartados, e runs medidos e validados. Apenas
os runs válidos entram nas estatísticas e nas amostras brutas em
nanossegundos; preflight e warmups não entram em minimum, maximum, mean,
median ou p95.

Os sete workloads oficiais serão usados pelo mesmo caminho estrutural em O0 e
O1, variando somente o nível solicitado. A integração nativa atual já exercita
o workload oficial `minimal` em O0 e O1 com build único e reutilização do mesmo
ELF. Build, execução, validação, cálculo estatístico e serialização permanecem
responsabilidades separadas. A instrumentação de benchmark deverá usar as
interfaces públicas existentes e não criará opções experimentais na CLI apenas
para facilitar medições.

Tempos e comparações percentuais serão informativos, nunca thresholds rígidos
de CI. Timeout continuará permitido como proteção contra travamento. Correção
funcional, execução completa dos casos, zero skips nativos e validade dos
formatos poderão atuar como gates determinísticos.

O modo público `elf-execution` ainda não está disponível no runner. O JSON
público do runner continua inalterado em `benchmark_format_version 1.1.0` e
não expõe os dados internos da E3. `cli-end-to-end` continua pendente. A E3
ainda é parcial, e E4 e E5 não foram iniciadas.

O baseline determinístico continuará livre de tempos e informações ambientais.
Resultados temporais poderão ser emitidos localmente, em logs ou artefatos
efêmeros de CI e em JSON não versionado; eles não serão rastreados por padrão.
Esta seção não apresenta comandos ou opções futuras como se já existissem.

## Comandos

```bash
python tools/benchmark.py --help
python tools/benchmark.py --list
python tools/benchmark.py --mode hosted-pipeline --optimization both --workload all --warmups 3 --runs 10
```

Quando invocado com `--optimization both`, o runner executa ambas as configurações (O0 e O1) e emite uma comparação neutra com razões informativas de proporção temporal e volumétrica (crescimento ou decréscimo estrutural).

Para adicionar um novo workload: crie um arquivo `.s3` em `benchmarks/` e registre-o com o respectivo id e constraints no array dentro de `benchmarks/manifest.json`.
