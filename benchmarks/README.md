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

## Contrato planejado da E3

A E3 está formalmente aberta, mas ainda não foi implementada. A implementação
futura separará duas superfícies:

- `cli-end-to-end`: medição da experiência completa de um comando público já
  existente, incluindo os custos reais atravessados por esse comando;
- `elf-execution`: medição exclusiva de um ELF Linux x86-64 previamente
  construído e validado, sem incluir build ou inicialização da CLI na amostra.

Para a execução isolada, cada combinação de workload e O0/O1 deverá construir
o ELF antes do loop. O artefato será validado, reutilizado nos warmups e então
reutilizado nas amostras medidas. Warmups não entram nas estatísticas e uma
amostra funcionalmente inválida não pode ser incorporada a minimum, maximum,
mean, median ou p95.

Os sete workloads oficiais serão usados pelo mesmo caminho estrutural em O0 e
O1, variando somente o nível solicitado. Build, execução, validação, cálculo
estatístico e serialização permanecerão responsabilidades separadas. A
instrumentação de benchmark deverá usar as interfaces públicas existentes e
não criará opções experimentais na CLI apenas para facilitar medições.

Tempos e comparações percentuais serão informativos, nunca thresholds rígidos
de CI. Timeout continuará permitido como proteção contra travamento. Correção
funcional, execução completa dos casos, zero skips nativos e validade dos
formatos poderão atuar como gates determinísticos.

O baseline determinístico continuará livre de tempos e informações ambientais.
Resultados temporais poderão ser emitidos localmente, em logs ou artefatos
efêmeros de CI e em JSON não versionado; eles não serão rastreados por padrão.
Esta seção estabelece o contrato da implementação futura e não apresenta
comandos ou opções futuras como se já existissem.

## Comandos

```bash
python tools/benchmark.py --help
python tools/benchmark.py --list
python tools/benchmark.py --mode hosted-pipeline --optimization both --workload all --warmups 3 --runs 10
```

Quando invocado com `--optimization both`, o runner executa ambas as configurações (O0 e O1) e emite uma comparação neutra com razões informativas de proporção temporal e volumétrica (crescimento ou decréscimo estrutural).

Para adicionar um novo workload: crie um arquivo `.s3` em `benchmarks/` e registre-o com o respectivo id e constraints no array dentro de `benchmarks/manifest.json`.
