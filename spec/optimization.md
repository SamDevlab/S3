# Análise e otimização S3 0.5

Status: normativo.

## Inicialização

Análise sobre CFG verificada classifica cada elemento como `UNINITIALIZED`,
`INITIALIZED` ou `MAYBE_INITIALIZED`. Loads definitivamente inválidos e segunda
inicialização imutável definitivamente repetida são erros estáticos. Incerteza,
índices dinâmicos e joins parciais conservam checks de runtime.

Constantes de índice podem atravessar `CONST`, `MOVE`, `INVERT` e `ADD` sem
overflow. O ponto fixo de loops independe da ordem textual.

## O0

É o padrão. Preserva a IR baixada e executa verificação/análise de segurança.

## O1

Pode fazer folding e propagação local de constantes, DCE de instruções puras,
remoção de blocos inalcançáveis, threading de saltos triviais e remoção dos
registros mortos correspondentes. A IR é verificada antes e depois.

Não pode remover/reordenar efeitos (`CALL`, `LOAD`, `STORE`, terminadores) nem
checks de overflow, faixa, bounds, inicialização, imutabilidade, frame limit ou
estado trit. Folding que esconderia overflow é proibido.

Equivalência semântica exigida quando as execuções terminam dentro do
orçamento:

```text
emulador O0 = emulador O1 = nativo O0 = nativo O1
```

Para falhas semânticas, categoria e local lógico devem ser equivalentes.

## Orçamento de instruções do Marco 0.7

Implementado e validado no Marco 0.7.

O orçamento conta opcodes do S3 Assembly efetivamente selecionado depois de O0
ou O1. Como O1 pode remover instruções, limites baixos podem ser esgotados em
pontos diferentes. Essa diferença de uma falha por limite de recurso é
permitida.

A equivalência continua obrigatória quando ambas as execuções terminam dentro
do orçamento. Exaustão não autoriza resultado diferente, diferença semântica,
corrupção de estado nem efeitos do opcode excedente.

## Otimizações baseadas em evidências (Marco 0.8)

Qualquer alteração ou adição nos passes de O1 será estritamente avaliada pelas
métricas isoladas e normativas da infraestrutura de medição do Marco 0.8, não
sendo admitidas otimizações às cegas ou especulativas na linguagem S3 que não
possuam comprovação em relatórios de desempenho oficiais.
