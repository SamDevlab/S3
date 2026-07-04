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

O limite padrão é 2187 trits lógicos por frame. O custo de um objeto é
`length × 1` para trit e `length × 6` para tryte.

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

## Fronteira futura

O modelo não define tamanho em bits, ordem de bytes, padding, stack pointer ou
endereços assinados/não assinados. Backends futuros mapearão objetos lógicos a
endereços físicos sob ADR próprio.
