# Modelo ternário balanceado

Status: normativo.

## Representação

Um trit pertence a `{-1, 0, 1}`. Um tryte é a sequência:

```text
(t0, t1, t2, t3, t4, t5)
```

na qual `t0` é o trit menos significativo. O valor decimal é:

```text
t0·3^0 + t1·3^1 + t2·3^2 + t3·3^3 + t4·3^4 + t5·3^5
```

Essa ordem é o contrato das funções de conversão da implementação de
referência. Ela não define ainda uma ordem de bytes ou ABI de memória.

## Conversão decimal

Para cada posição, divide-se o valor por 3. Restos `0` e `1` são dígitos
diretos. Resto `2` é substituído por `-1` e incrementa o quociente. O processo
é repetido por seis posições e preenchido com zeros.

Todo valor no intervalo `[-364, 364]` possui uma representação única de seis
trits. Valores externos são rejeitados.

## Operações

- inversão: troca cada `-1` por `1`, preserva `0` e troca `1` por `-1`;
- soma: soma matemática dos valores, com erro se o resultado não couber;
- mínimo: `min` independente por posição;
- máximo: `max` independente por posição;
- comparação: sinal da diferença matemática, sem realizar subtração na IR.

As identidades normativas são:

```text
~~x = x
x + 0 = x
x + (~x) = 0
compare(x, x) = 0
compare(x, y) = ~compare(y, x)
min(x, y) = min(y, x)
max(x, y) = max(y, x)
```

## Overflow

Overflow é uma condição de erro detectável. Não há saturação, wraparound,
promoção implícita nem comportamento indefinido. Constantes são verificadas na
análise semântica e cada escrita de registrador é verificada no emulador.

## Armazenamento lógico

No modelo de memória 0.3, `trit` custa um trit lógico e `tryte` custa seis. A
ordem conceitual dos seis trits continua menos significativo primeiro. Isso não
define ordem de bytes, packing binário ou layout físico de backend.
