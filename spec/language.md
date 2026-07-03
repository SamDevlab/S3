# Especificação da linguagem S3 0.2

Status: normativa para o subconjunto bootstrap.

## Unidade de compilação e funções

Uma unidade contém uma ou mais funções e exatamente uma `main`, que não recebe
parâmetros. Nomes de função são únicos; não há sobrecarga.

```s3
fn add(a: tryte, b: tryte) -> tryte {
    return a + b;
}
```

As assinaturas de todas as funções são coletadas antes da análise dos corpos.
Logo, uma função pode chamar outra declarada posteriormente e pode chamar a si
mesma. Parâmetros são locais imutáveis do escopo da função e não podem ser
redeclarados nesse mesmo escopo.

Chamadas são expressões e os argumentos são avaliados da esquerda para a
direita:

```s3
add(10, double(2))
```

Quantidade e tipos devem coincidir exatamente com a assinatura. Não há
conversões implícitas entre `trit` e `tryte`, valores de função ou chamadas
indiretas.

## Léxico

Palavras-chave: `fn`, `return`, `switch`, `trit`, `tryte`.

Identificadores seguem `[A-Za-z_][A-Za-z0-9_]*`. Inteiros são sequências
decimais não negativas. O lexer reconhece:

```text
->  <=>  ~  &  |  +  -  =  (  )  {  }  :  ;  ,
```

Espaços e comentários `//` são ignorados. Cada token preserva texto original,
linha/coluna iniciadas em 1 e posição absoluta em pontos de código iniciada em
0.

O sinal nunca integra o literal: `-1` continua sendo `MINUS`, `INTEGER("1")`.
No rótulo de caso, o parser reúne especificamente sinal opcional e inteiro.

## Tipos e overflow

`trit` representa `-1`, `0` ou `1`. `tryte` representa seis trits e o intervalo
`[-364, 364]`. Não existem tipos unsigned.

Literais assumem o tipo exigido pelo contexto; sem contexto, assumem `tryte`.
Literal fora da faixa é erro semântico. Resultado aritmético fora da faixa é
erro detectável em execução, sem wraparound ou saturação.

## Blocos, escopos e retorno

Declarações são imutáveis e visíveis após sua ocorrência no bloco. Cada caso de
`switch` abre um escopo filho. Seus nomes não são visíveis em outro caso nem
depois do `switch`.

Uma função é válida somente se todos os caminhos possíveis terminarem em
`return`. Um `switch` é terminador quando seus três blocos terminam. Comando
posterior a `return` ou a `switch` totalmente terminador é erro de código
inalcançável.

## Switch ternário

```s3
switch (value <=> 0) {
    -1: { return -1; }
    0:  { return 0; }
    1:  { return 1; }
}
```

Regras:

- o seletor deve ter tipo `trit` e é avaliado uma vez;
- os rótulos válidos são somente `-1`, `0` e `1`;
- os três são obrigatórios e únicos, em qualquer ordem;
- cada caso possui bloco e escopo próprios;
- exatamente um caso é executado;
- não há `default` nem fallthrough.

## Expressões

Precedência, da maior para a menor:

1. chamadas, primários e parênteses;
2. unários `~` e `-`;
3. `+` e `-`;
4. mínimo tritwise `&`;
5. máximo tritwise `|`;
6. comparação `<=>`.

Operadores binários exigem operandos do mesmo tipo. `<=>` sempre retorna
`trit`. `~x` e `-x` são inversão ternária. A subtração da fonte:

```text
a - b
```

é obrigatoriamente reduzida para:

```text
ADD(a, INVERT(b))
```

Não existe opcode de subtração após o lowering.

## Diagnósticos

Erros de compilação preservam linha e coluna para chamadas, argumentos,
comparações, switches, casos e retornos. São diagnosticados, entre outros:
função/variável inexistente, função duplicada, parâmetro duplicado, uso de
função como variável, chamada de variável, aridade/tipo incorretos, casos
inválidos/ausentes/duplicados, seletor não `trit`, retorno incompatível, caminho
sem retorno e código inalcançável.

