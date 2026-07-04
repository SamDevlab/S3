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

Equivalência exigida:

```text
emulador O0 = emulador O1 = nativo O0 = nativo O1
```

Para falhas, categoria e local lógico devem ser equivalentes.

