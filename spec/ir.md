# S3 IR 0.6

Status: normativo.

## Estrutura

`IRModule` contém funções. Cada função declara parâmetros, registradores SSA,
objetos de memória e blocos básicos. `entry` é obrigatório.

Registradores possuem tipo `trit`/`tryte` e definição única. Parâmetros são
definições disponíveis em todos os blocos alcançáveis.

```text
IRMemoryObject:
    index
    element_type
    length
    mutable
    source
```

Objetos são locais à função/frame, têm comprimento entre 1 e 365 e não são
valores: não podem ser passados, retornados ou usados por operadores.

## Instruções

Operações de valor:

```text
CONST MOVE INVERT ADD MINIMUM MAXIMUM COMPARE CALL
```

Toda instrução que produz valores possui o campo canônico `results`, uma lista
ordenada de registradores de resultado. O campo singular `result` permanece
apenas como compatibilidade estrutural para largura 1 e deve concordar com
`results[0]` quando ambos aparecem. `CALL` pode produzir zero resultados
quando o grupo completo é descartado, um resultado scalar ou N resultados de um
valor agregado; ela continua sendo uma única instrução e executa uma única vez.

Memória:

```text
LOAD  result, memory, index
STORE memory, index, value
```

`LOAD` produz o tipo do elemento. `STORE` não produz resultado. Índices são
`tryte`. O marcador `initialization=true` distingue stores iniciais permitidos
em objetos imutáveis; escrita comum neles é rejeitada pelo verificador.

Terminadores:

```text
RETURN JUMP BRANCH3
```

`RETURN` carrega a lista completa de operandos do valor lógico retornado. A
largura deve bater exatamente com a assinatura da função; retorno parcial,
operando extra e truncagem são inválidos.

Cada bloco termina exatamente uma vez. `BRANCH3` usa `trit` e destinos
distintos na ordem negativo, neutro, positivo. Ciclos são válidos; terminação
dinâmica é protegida pelo limite de instruções.

Não existem `SUBTRACT`, `PHI`, ponteiros, casts ou aritmética de endereço.

## Dominância

O verificador constrói sucessores e predecessores, encontra blocos alcançáveis
por busca desde `entry` e calcula dominadores por ponto fixo:

```text
dom(entry) = {entry}
dom(B) = {B} ∪ interseção(dom(P)) para predecessores alcançáveis P
```

Regras:

- parâmetro domina todo bloco alcançável;
- definição no mesmo bloco precede o uso;
- definição em outro bloco deve dominar o bloco de uso;
- valor definido num único ramo não pode ser usado no join;
- bloco inalcançável ainda recebe validação estrutural/tipos; uso cruzado
  não-paramétrico nele é rejeitado conservadoramente.

Comunicação entre ramos usa objeto de memória, não `PHI`.

## Artefato JSON

A forma persistente usa envelope `s3-ir`, versão `0.6.0`, chaves ordenadas,
indentação de dois espaços e newline. Funções, parâmetros, registros, memória,
blocos, instruções, mutabilidade, origem, `result_types` e `results` são
explícitos. Cada função declara `result_types`, a lista ordenada de células do
valor lógico retornado; `return_type` permanece como alias width-1 e deve
corresponder à primeira célula.

Leitores aceitam o legado `0.5.0` somente para largura 1 e o normalizam para
`result_types = [return_type]` e `results = [result]` nas instruções produtoras.
Campos 0.6.0 sob envelope 0.5.0 são rejeitados. O leitor rejeita campos,
opcodes, tipos e versões desconhecidos e executa o verificador. Veja
`artifacts.md`.

## Inicialização e otimização

Após verificação, análise por CFG prova estados por elemento. Load constante
definitivamente não inicializado e segunda escrita imutável comprovada são
erros estáticos; incerteza mantém runtime check.

O0 preserva a IR e é padrão. O1 permite folding local válido, propagação,
eliminação de valor puro/morto, bloco inalcançável e trampolim. ADD que poderia
falhar, `CALL`, `LOAD`, `STORE` e terminadores permanecem. A IR otimizada é
verificada novamente. Veja `optimization.md`.

## Verificação estática e dinâmica

O verificador rejeita objetos duplicados/inválidos, referências inexistentes,
tipos de índice/valor/resultados incorretos, store comum em objeto imutável,
violação SSA/dominância, chamada/retorno inválido, ponteiros e subtração.

Bounds calculados e inicialização não comprovável permanecem dinâmicos. O
frontend inicializa declarações; emulador e nativo jamais devolvem célula não
inicializada.
