# Memória lógica S3 0.3

Status: normativo para o bootstrap.

## Objetos

Memória é uma coleção de objetos locais ao frame. Cada objeto declara:

```text
identificador, tipo de elemento, comprimento, mutabilidade
```

Tipos de elemento são somente `trit` e `tryte`; comprimento é positivo e
imutável, com máximo de 365 elementos devido ao índice `tryte` `0..364`. Não
existem endereços ou ponteiros como valores S3.

## Unidade, layout e alinhamento

- a unidade de acesso é um elemento tipado;
- `trit` ocupa logicamente 1 trit e possui alinhamento lógico 1;
- `tryte` ocupa logicamente 6 trits e possui alinhamento lógico 6;
- trytes seguem ordem de trits menos significativo primeiro;
- arrays dispõem elementos em índices consecutivos de `0` a `length - 1`;
- objetos são regiões lógicas separadas, sem offsets observáveis ou aliasing.

O limite padrão é 6561 trits lógicos (`3^8`) por frame. Ele comporta qualquer
objeto individual permitido, inclusive `tryte[365]`, que custa 2190 trits
lógicos. O custo de um objeto é `length × 1` para trit e `length × 6` para
tryte. A soma dos custos de todos os objetos do frame não pode exceder o limite,
que permanece configurável pela API do emulador.

## Inicialização e acesso

Elementos começam não inicializados. Uma leitura antes da primeira escrita é
erro. Declarações de fonte sempre inicializam todos os elementos.

Índices têm tipo `tryte`. Índice negativo ou `>= length` é erro. Literais
constantes inválidos são rejeitados pelo frontend; valores calculados são
verificados pelo emulador.

Objeto imutável aceita somente a primeira inicialização de cada célula. Objeto
mutável aceita escritas posteriores. Tipo e faixa do valor são sempre
verificados.

## Tempo de vida e isolamento

Objetos são alocados ao criar um frame e descartados com ele. Chamadas,
inclusive recursivas, nunca compartilham objetos. Não há heap, memória global,
aliasing, ponteiros, referências ou aritmética de endereço.

## Mapeamento nativo x86-64

O modelo lógico não define universalmente tamanho em bits, ordem de bytes,
padding ou stack pointer. O backend Linux x86-64 faz um mapeamento específico:

```text
trit  → int8
tryte → int16
```

Arrays são contíguos no frame e cada elemento possui um byte físico de
inicialização. Esses bytes, slots de registradores e padding não alteram o
custo lógico. Outros backends podem mapear os mesmos objetos de modo diferente
sob ADR próprio; veja ADR-0007 e `native-x86_64.md`.
