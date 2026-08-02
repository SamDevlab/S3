# S3 Assembly textual 0.6

Status: normativo para o bootstrap.

## Declarações

```asm
.s3asm 0.6.0

.function pair -> [tryte, trit]
    .register r0, tryte
    .register r1, trit
.label entry
    TCONST r0, 6
    TCONST r1, -1
    TRET   [r0, r1]
.end
```

`.param` e `.register` declaram registradores. `.memory` declara:

```text
.memory mN, trit|tryte, comprimento, mutable|immutable
```

O quarto campo é emitido pelo renderer; se omitido em assembly manual, o parser
assume `mutable`. Declarações antecedem labels/instruções. Objetos e
registradores são locais ao frame. Comprimentos válidos estão entre 1 e 365.

O renderer sempre emite `.s3asm 0.6.0` antes das funções. O parser aceita
também o legado `.s3asm 0.5.0` para funções width-1 e normaliza assembly 0.1–0.4
sem cabeçalho para essa forma escalar. Versão malformada, desconhecida ou major
incompatível é erro.

## Instruções

Mantidas:

```text
TCONST TMOV TINV TADD TMIN TMAX TCMP TCALL TRET TJMP TBR3
```

Funções declaram um grupo ordenado de tipos de resultado: `.function f ->
tryte` é a forma escalar; `.function f -> [tryte, trit]` é a forma agregada.
`TCALL` materializa o grupo completo em um grupo de destinos, ou descarta o
grupo completo com `[]`. `TRET` retorna todos os operandos em ordem. É inválido
consumir parcialmente, descartar parcialmente, duplicar uma chamada por célula
ou truncar o grupo para a primeira célula.

```asm
TCALL [r2, r3], pair
TCALL [], pair
TRET  [r2, r3]
```

Memória:

```text
TLOAD  r_destination, m_object, r_index
TSTORE m_object, r_index, r_source
```

O índice deve ser registrador `tryte`; destino/fonte deve corresponder ao tipo
do objeto. Bounds e inicialização são validados em execução. Em objeto
imutável, o primeiro store de cada célula inicializa; outro store falha.

Não existem `TSUB`, `TPTR` ou `TCAST`.

## Estrutura, ciclos e origem

Cada bloco termina com `TRET`, `TJMP` ou `TBR3`; cada função contém ao menos um
`TRET`. Ciclos estruturais são permitidos e execuções sem retorno são
interrompidas pelo limite de instruções.

Toda função começa semanticamente no bloco `entry`, independentemente da ordem
textual. O backend nativo emite salto explícito do prólogo para esse label.

Metadado opcional:

```asm
; source=linha:coluna:offset
```

é preservado pelo round-trip e incluído em diagnósticos.

O exemplo recursivo normativo completo está em
`examples/assembly_recursive_sum.s3asm`, é analisado e executado pela suíte e
retorna `10`.

## Compatibilidade

Assembly 0.1 sem labels recebe bloco implícito `entry`; assembly 0.2 sem memória
continua válida. Assembly 0.5 permanece válido apenas como formato escalar
width-1. Sintaxe de grupos de resultado sob header 0.5 é rejeitada. Todos os
registradores, objetos, labels e assinaturas são validados antes da execução.

## Backend nativo

O S3 Assembly validado é o contrato de entrada do backend Linux x86-64. Todos
os opcodes listados acima possuem emissão nativa; o backend não reinterpreta
AST nem repete semântica de fonte. Width-1 retorna em `RAX`; width > 1 usa uma
área de retorno do chamador passada por argumento oculto interno ao backend.
Esse ponteiro não aparece na linguagem fonte nem no Assembly. Antes de emitir,
o backend valida programa completo, `main` sem parâmetros e retorno escalar,
tipos, chamadas, CFG, objetos e cota lógica.

A representação física, ABI, checks e runtime estão em
[`native-x86_64.md`](native-x86_64.md). Esse target não adiciona diretivas nem
opcodes ao formato e continua rejeitando `TSUB`.

## Fixed array source values

S3 Assembly has no source-level array value token. A fixed array crossing a
function boundary is emitted as its complete ordered scalar parameter or result
group. Local indexed arrays continue to use `.memory`, `TLOAD`, and `TSTORE`.

The 0.6 function, `TCALL`, and `TRET` group syntax is sufficient. Legacy 0.5
reading remains width-one only; no new 0.5 encoding is introduced.

## Experimental tokenizer boundary

The Milestone 1.14 tokenizer is an incremental bounded-text component for the
future self-hosted Assembly parser. It is additive and experimental: the Python
Assembly parser in `bootstrap.s3.assembly` remains the normative reader.

The tokenizer recognizes only the existing textual surface described above:
directives, version numbers, identifiers, register names, memory/static value
names, scalar decimal integers, group punctuation, LF/CRLF, and `;` comments.
Opcode names such as `TCALL` and `TRET` are lexical identifiers at this stage;
parser validation classifies them later. The tokenizer adds no new directives,
opcodes, value syntax, version, heap allocation, source pointers, filesystem
behavior, or default compiler path.
