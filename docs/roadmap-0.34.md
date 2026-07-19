# S3 0.34

Status: open

## Objetivo
Construir um laboratório real e reproduzível para investigar a hipótese de que a divisão de um intervalo numérico em caixas/segmentos contíguos pode melhorar o uso de cache e permitir processamento paralelo eficiente na busca de números primos.

## O que será implementado
- Crivo simples sequencial.
- Crivo segmentado sequencial.
- Crivo segmentado paralelo.
- Ferramenta de benchmark CLI para testar diferentes tamanhos de segmento e quantidades de workers.
- Coleta de métricas (desempenho, uso de memória, speedup, eficiência).
- Detecção de GPU via OpenCL / Vulkan (opcional).

## O que NÃO será implementado
- Novo algoritmo de primalidade gigantesco para um único número.
- Arrays dinâmicos, Heap, GC.
- Suporte a renderer textual.

## Validação
- Testes automatizados focados no checksum e limites de primalidade conhecidos.
- Benchmark local medido, sem tornar tempos rígidos como portões de CI.
