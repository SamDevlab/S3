# S3 Assembly textual 0.3

Status: normativo para o bootstrap.

## Declarações

```asm
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 10
    TSTORE m0, r0, r1
    TLOAD  r2, m0, r0
    TRET   r2
.end
```

`.param` e `.register` declaram registradores. `.memory` declara:

```text
.memory mN, trit|tryte, comprimento, mutable|immutable
```

O quarto campo é emitido pelo renderer; se omitido em assembly manual, o parser
assume `mutable`. Declarações antecedem labels/instruções. Objetos e
registradores são locais ao frame. Comprimentos válidos estão entre 1 e 365.

## Instruções

Mantidas:

```text
TCONST TMOV TINV TADD TMIN TMAX TCMP TCALL TRET TJMP TBR3
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
continua válida. Todos os registradores, objetos, labels e assinaturas são
validados antes da execução.
