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

O threading pode substituir um `BRANCH3` por `JUMP` quando os três destinos,
depois de atravessar apenas blocos de salto vazios, convergem comprovadamente
para o mesmo bloco. Convergências parciais permanecem inalteradas.

O1 também pode remover `STORE`s de objetos de memória locais quando a função
inteira não contém nenhum `LOAD` para o mesmo objeto. A prova depende da
ausência de ponteiros e do isolamento por frame; objetos que possuem qualquer
`LOAD` permanecem fora dessa regra.

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

Qualquer alteração ou adição nos passes de O1 deve ser avaliada com as
métricas da infraestrutura de medição do Marco 0.8. As métricas temporais são
informativas, enquanto métricas determinísticas de estrutura gerada e
instruções executadas podem funcionar como gates de CI por meio do baseline
determinístico. Otimizações devem preservar a semântica e os contratos públicos
da linguagem S3 e ser acompanhadas por evidências reproduzíveis.
