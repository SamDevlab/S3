# ADR-0011: inicialização conservadora e otimização O1

- Status: aceito
- Data: 2026-07-03

## Contexto

O runtime precisa continuar seguro para assembly manual, mas a IR permite
provar alguns erros antes da execução. Otimizações também são úteis, desde que
não alterem overflow, bounds, inicialização, imutabilidade ou ordem de efeitos.

## Análise de inicialização

Uma análise de fluxo por função usa o lattice:

```text
UNINITIALIZED < MAYBE_INITIALIZED
INITIALIZED   < MAYBE_INITIALIZED
```

O estado é por elemento de objeto. Entrada começa não inicializada. `STORE` com
índice constante marca o elemento; `LOAD` definitivamente não inicializado é
erro estático; estado talvez inicializado mantém check de runtime. Join só é
inicializado quando todos os predecessores dizem isso. Loops usam ponto fixo
determinístico.

Propagação limitada de `CONST`, `MOVE`, `INVERT` e `ADD` reconhece índices
constantes sem ocultar overflow. Store dinâmico não prova elemento específico.
Segunda inicialização comprovada de elemento imutável é erro; incerteza mantém
o check. A análise não remove checks nativos.

## Níveis de otimização

`O0` é o padrão e apenas verifica/preserva a IR. `O1` roda depois de uma
verificação e é verificado novamente. Pode:

- propagar/foldar constantes em `MOVE`, `INVERT`, `ADD`, `MINIMUM`, `MAXIMUM`
  e `COMPARE`, apenas quando o resultado é canônico;
- remover instruções puras com resultado morto;
- remover blocos inalcançáveis;
- redirecionar saltos por blocos vazios que apenas saltam;
- remover registros cujas definições foram eliminadas.

`MOVE x, x` é removível no modelo geral; a IR SSA verificada normalmente o
proíbe por redefinição. Overflow não é folded: a operação original permanece
para produzir o mesmo erro. `CALL`, `LOAD`, `STORE` e terminadores não são
apagados nem reordenados. Checks de runtime e origem útil são preservados.

## Consequências

O1 é local, previsível e não tenta alocação sofisticada, TCO ou PHI. O ganho
pode ser modesto; correção diferencial entre O0/O1, emulador e nativo é o
critério. Otimizações interprocedurais permanecem fora do marco.

