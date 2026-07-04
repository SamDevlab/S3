# Especificação da linguagem S3 0.3

Status: normativa para o bootstrap.

## Funções e tipos escalares

Uma unidade contém funções com nomes únicos e exatamente uma `main` sem
parâmetros. Assinaturas são coletadas antes dos corpos, permitindo forward
calls e recursão. Parâmetros e retornos são somente `trit` ou `tryte`.

`trit` representa `-1`, `0`, `1`; `tryte` representa `[-364, 364]`. Não há
conversão implícita nem tipos unsigned. Overflow continua sendo erro.

## Léxico

Palavras-chave:

```text
fn return switch mut trit tryte
```

Símbolos:

```text
-> <=> ~ & | + - = ( ) { } [ ] : ; ,
```

Identificadores seguem `[A-Za-z_][A-Za-z0-9_]*`. Comentários começam em `//`.
Linha/coluna e offset são preservados. O sinal nunca faz parte do inteiro:
`[-1]` contém `LEFT_BRACKET`, `MINUS`, `INTEGER`, `RIGHT_BRACKET`.

## Bindings e mutabilidade

Declarações são imutáveis por padrão:

```s3
tryte value = 10;
```

`mut` permite atribuição posterior:

```s3
mut tryte value = 10;
value = value + 1;
```

Atribuição é statement e não produz valor. O alvo deve existir, ser mutável e
ter o mesmo tipo do valor. Parâmetros, funções e bindings imutáveis não podem
ser atribuídos. Toda declaração exige inicializador.

Escopos continuam lexicais. Uma atribuição em caso de `switch` pode alcançar
mutável declarado em escopo pai.

## Arrays estáticos

```s3
mut tryte[4] values = [1, 2, 3, 4];
values[1] = 5;
return values[0];
```

Regras:

- elemento somente `trit` ou `tryte`;
- comprimento entre 1 e 365, conhecido na compilação;
- uma dimensão; arrays aninhados são erro;
- literal obrigatório com exatamente o comprimento declarado;
- elementos avaliados da esquerda para a direita e tipados individualmente;
- arrays imutáveis podem ser lidos, mas não alterados;
- somente arrays mutáveis aceitam atribuição indexada;
- não há atribuição/cópia de array inteiro;
- arrays não são argumentos, retornos ou operandos;
- somente a indexação produz escalar;
- índice tem tipo `tryte`;
- índice constante fora de `[0, length)` é erro semântico;
- índice calculado fora da faixa é erro de execução.

## Expressões e precedência

Da maior para a menor:

1. chamada, indexação, primários e parênteses;
2. `~` e `-` unários;
3. `+` e `-`;
4. `&`;
5. `|`;
6. `<=>`.

Um identificador aceita no máximo um sufixo postfix no subconjunto atual:
chamada ou indexação. Chamadas aninhadas continuam possíveis nos argumentos.

`<=>` retorna `trit`. `&`/`|` são mínimo/máximo tritwise. Subtração é reduzida
exclusivamente a `INVERT` seguido de `ADD`; não existe opcode de subtração.

## Controle ternário e retorno

`switch` exige seletor `trit`, avaliado uma vez, e exatamente os casos únicos
`-1`, `0`, `1`, sem default ou fallthrough. Cada caso cria escopo.

Todas as rotas da função devem retornar. Código após retorno ou switch cujos
três casos retornam é inalcançável. Um mutável declarado antes do switch pode
receber stores nos ramos e ser lido após o join sem `PHI`.

## Diagnósticos

São erros: atribuição inválida, tipo incompatível, array mal formado, array em
contexto escalar, índice constante inválido, caso ternário inválido, chamada
incorreta, caminho sem retorno e código inalcançável. Diagnósticos de
compilação incluem origem S3; falhas dinâmicas de memória incluem função,
bloco, opcode, origem, objeto, índice e comprimento quando disponíveis.
