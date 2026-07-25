# Diagnósticos nativos S3 0.5

Status: normativo para Linux x86-64.

## Formato

Erros usam stderr e status 1:

```text
runtime error [bounds] in function 'read'
at source 4:12 (block entry, TLOAD): index -1 outside [0, 2)
```

Sem metadado:

```text
runtime error [uninitialized memory] in function 'main'
at source unknown (block entry, TLOAD): index 0 is uninitialized in m0
```

Função, bloco, opcode, categoria e origem são determinados na compilação.
Valores como índice e resultado são formatados em decimal assinado no runtime.
Linha assembly é preservada quando veio do parser textual; origem S3 usa linha
e coluna, sem inventar dados ausentes.

## IDs e dados

Cada check recebe ID crescente na travessia canônica do programa. Strings
estáticas são labels locais determinísticos. IDs não derivam de endereços,
hashes, aleatoriedade ou ordem de mapas.

## Categorias

```text
overflow
bounds
uninitialized register
uninitialized memory
immutable memory
invalid trit state
frame limit
invalid runtime state
```

Falha ocorre antes de acesso perigoso ou publicação de valor inválido. Não há
traceback, libc, C ou Python no executável.

## Limite de instruções

O runtime reporta a categoria:

```text
instruction limit
```

A falha ocorre no site do opcode S3 correspondente, antes de seus efeitos, e usa
stderr e status 1. O diagnóstico informa limite, função, bloco, opcode e
origem quando disponíveis. O formato é textual:

```text
runtime error [instruction limit] in function 'main'
at source 3:5 (block entry, TJMP): limit 100000 exceeded
```

Em `run-native --diagnostic-format json`, a CLI hospedada continuará emitindo
`S3E_NATIVE_PROCESS_FAILED` e preservando este stderr em `notes`, sem analisar
ou converter semanticamente o texto do ELF.
