# S3 IR 0.3

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

## Verificação estática e dinâmica

O verificador rejeita objetos duplicados/inválidos, referências inexistentes,
tipos de índice/valor/resultados incorretos, store comum em objeto imutável,
violação SSA/dominância, chamada/retorno inválido, ponteiros e subtração.

Inicialização por caminho e bounds calculados são dinâmicos. O frontend
inicializa todas as declarações; o emulador jamais devolve célula não
inicializada.
