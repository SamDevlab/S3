# Backend nativo Linux x86-64 0.4

Status: normativo para o backend experimental.

## Fronteira

O pipeline nativo é:

```text
fonte S3
→ frontend
→ IR verificada
→ S3 Assembly validada
→ GNU assembly x86-64
→ ELF Linux x86-64
```

O compilador é executado em Python. O GNU assembly e o ELF produzidos não
dependem de Python, não contêm interpretador, não passam por C e não usam LLVM.
O backend aceita somente `AssemblyProgram` completamente validado.

## Representação

Em objetos de memória, `trit` é `int8` e `tryte` é `int16`; arrays são
contíguos. Slots de registradores virtuais e cálculos usam inteiros assinados
de 64 bits. Loads estendem sinal, e valores publicados são canônicos:

```text
trit  [-1, 1]
tryte [-364, 364]
```

O modelo físico é específico deste target. Memória lógica continua custando
um trit por `trit`, seis por `tryte`, com limite padrão de 6561 por frame.

## ABI e frames

Funções `nome` possuem símbolo `s3_nome`. System V AMD64 transporta os seis
primeiros argumentos em `RDI`, `RSI`, `RDX`, `RCX`, `R8` e `R9`; excedentes
seguem na pilha. O retorno usa `RAX`. O chamador mantém alinhamento de 16 bytes.

O frame, calculado deterministicamente, contém slots de valores, flags de
inicialização de registradores, dados de objetos e um byte de inicialização
por elemento. Regiões seguem ordem numérica, respeitam alinhamento próprio e
não se sobrepõem. O tamanho final é múltiplo de 16. Cada chamada cria um frame
novo.

## Instruções

| S3 Assembly | Emissão x86-64 |
|---|---|
| `TCONST` | constante validada para slot |
| `TMOV` | load verificado e cópia |
| `TINV` | negação assinada e check de faixa |
| `TADD` | soma assinada e check de faixa |
| `TMIN`, `TMAX` | comparação para trit; helper tritwise para tryte |
| `TCMP` | comparação assinada, resultado exato -1/0/1 |
| `TJMP` | salto para label local |
| `TBR3` | validação e dispatch de -1/0/1 |
| `TCALL` | chamada System V, inclusive argumentos na pilha |
| `TRET` | valor em `RAX`, epílogo e retorno |
| `TLOAD` | bounds, inicialização e load com extensão de sinal |
| `TSTORE` | bounds, imutabilidade, store estreito e marca de inicialização |

Não existe `TSUB`; subtração continua reduzida a `TINV` seguido de `TADD`.
`TMIN` e `TMAX` de trytes decompõem seis trits balanceados, combinam cada
posição e reconstroem o inteiro.

## Runtime

`_start` chama `s3_main`, imprime `program returned: N` com newline por syscalls
Linux `write` e encerra por `exit`. Erros de overflow, bounds, registro ou
memória não inicializados, store imutável e estado ternário inválido produzem
mensagem em stderr e status 1. Não há libc.

## Toolchain e determinismo

O build exige host Linux x86-64 e um driver `cc`, `gcc` ou `clang` capaz de
montar GNU assembly e ligar com `-nostdlib -no-pie`. Descoberta e execução usam
listas de argumentos sem shell. Ausência de plataforma/toolchain gera
diagnóstico do compilador, não traceback interno.

A mesma entrada produz texto idêntico: não há timestamps, paths temporários,
aleatoriedade ou iteração instável. Arquivos temporários são removidos; o
assembly pode ser preservado explicitamente.

## Limites

Somente Linux x86-64 ELF é suportado. Não há Windows, macOS, ARM64, linker ou
assembler próprio, geração direta de ELF, ABI C pública, heap, globals,
ponteiros, I/O na linguagem, depurador, JIT, otimização avançada ou
autohospedagem.

