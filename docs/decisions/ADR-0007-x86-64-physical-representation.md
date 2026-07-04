# ADR-0007: representação física no backend x86-64

- Status: aceito
- Data: 2026-07-03

## Contexto

O modelo lógico do S3 define trits balanceados e trytes de seis trits, mas não
prescreve bytes, endianness ou packing. O primeiro backend binário precisa de
uma representação simples, auditável e compatível com os checks do emulador
sem transformar uma escolha para máquinas binárias na definição universal da
linguagem.

## Alternativas

- dois bits por trit reduziriam espaço, mas exigiriam encoding inválido,
  extração e atualização read-modify-write;
- packing de vários trits seria compacto, porém complicaria bounds, stores e
  depuração;
- representar todo valor por inteiro decimal de 64 bits simplificaria contas,
  mas desperdiçaria memória e esconderia a diferença física entre os tipos;
- um byte por `trit` e uma palavra de 16 bits por `tryte` deixam cada elemento
  diretamente endereçável e suas faixas cabem com folga.

## Decisão

No target experimental Linux x86-64:

```text
trit  em memória = inteiro assinado de 8 bits
tryte em memória = inteiro assinado de 16 bits
```

Os únicos valores canônicos continuam sendo:

```text
trit  ∈ [-1, 1]
tryte ∈ [-364, 364]
```

Arrays usam elementos contíguos em ordem crescente:

```text
trit[N]  = N bytes
tryte[N] = 2N bytes
```

Registradores virtuais e temporários de cálculo usam slots ou registradores
x86-64 assinados de 64 bits. Loads físicos fazem extensão de sinal. Uma
operação que produz valor S3 valida a faixa do tipo antes de publicar o
resultado; stores físicos escrevem somente depois dos checks.

Essa representação é do backend binário x86-64. Ela não altera o modelo
matemático, não afirma como hardware ternário armazenará trits e pode ser
substituída por outro backend. A cota lógica de 6561 trits por frame permanece
separada do número de bytes físicos, que também inclui slots e metadados.

## Consequências

O layout é deliberadamente pouco compacto, mas legível no assembly e simples
de testar. `TLOAD` e `TSTORE` calculam endereços com escala 1 ou 2. Cada
elemento possui ainda um byte de inicialização; isso preserva leitura
não inicializada e imutabilidade sem valores sentinela. O backend não expõe
esses endereços à linguagem.

