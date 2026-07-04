# ADR-0008: ABI e runtime nativos x86-64

- Status: aceito
- Data: 2026-07-03

## Contexto

O S3 Assembly possui chamadas tipadas, recursão, registradores virtuais e
objetos locais, mas não possui ABI física nem I/O. O backend 0.4 precisa gerar
ELF Linux executável sem libc, C, LLVM ou Python no processo final.

## Decisão

### Chamadas e símbolos

Chamadas geradas seguem System V AMD64. Valores S3 são transportados com
extensão de sinal em 64 bits:

```text
argumentos 1..6  = RDI, RSI, RDX, RCX, R8, R9
argumentos 7..N  = pilha, na ordem da ABI
retorno          = RAX
```

O chamador insere padding quando necessário, empilha argumentos excedentes em
ordem reversa e restaura `RSP` depois da chamada. Antes de `call`, `RSP` está
alinhado a 16 bytes. Não há limite lógico de aridade no backend.

Funções recebem símbolos `s3_<nome>`; `main` torna-se `s3_main`. Labels de
blocos são locais e incluem comprimentos e identificadores validados para não
colidir. Símbolos internos usam o prefixo reservado `__s3_`. Identificadores
somente chegam ao emitter depois do parser e validador do S3 Assembly.

### Frame

Cada função executa:

```asm
push rbp
mov  rbp, rsp
sub  rsp, frame_size
```

`frame_size` é múltiplo de 16. Uma etapa determinística de layout, independente
do emitter, reserva em ordem:

1. slots de 8 bytes dos registradores virtuais, por número crescente;
2. um byte de inicialização por registrador;
3. dados de cada objeto, por número crescente, com elementos de 1 ou 2 bytes;
4. um byte de inicialização por elemento de memória;
5. padding final para 16 bytes.

Regiões não se sobrepõem. Parâmetros são copiados para seus slots e marcados
como inicializados no prólogo; os demais metadados começam em zero. O backend
não precisa de área fixa para temporários no marco 0.4, mas o layout a modela
explicitamente. Objetos e metadados vivem no frame, logo recursão os isola.

Desde o Marco 0.5, toda função incrementa antes do prólogo um contador privado
de frames S3, limitado a 1024 por padrão, e todo retorno normal decrementa. O
prólogo transfere explicitamente controle para `entry`; ordem física dos
blocos não possui semântica.

O custo lógico da função é validado contra 6561 trits antes da emissão. O
tamanho físico inclui representação binária e metadados e não é essa cota.

### Checks

Toda leitura de registrador verifica inicialização. `TLOAD`/`TSTORE` verificam
índice não negativo e menor que o comprimento. Cada elemento de memória começa
não inicializado; load prematuro falha, e segundo store em elemento imutável
falha. Resultados de operações são validados como `trit` ou `tryte`.
`TBR3` aceita exclusivamente -1, 0 ou 1.

Falhas saltam para rotinas `__s3_fail_*`, escrevem uma categoria controlada em
stderr com a syscall `write` e encerram com status 1 pela syscall `exit`. Não
há acesso fora do objeto depois de um check falhar.

O Marco 0.5 especializa pontos de falha com IDs determinísticos e metadados de
função, bloco, opcode, origem ou linha assembly e valores relevantes. Origem
ausente é explicitamente desconhecida. ADR-0010 define o contrato atualizado.

### Entrada e saída

O ELF define `_start`, que chama `s3_main`, escreve exatamente:

```text
program returned: N\n
```

`N` é a representação decimal assinada do valor retornado por `main`. Por
exemplo:

```text
program returned: 6
program returned: -1
program returned: 0
```

Cada linha termina por newline. Depois da escrita, `_start` encerra com status
0. A conversão decimal, `TMIN`/`TMAX` tritwise de trytes,
mensagens e syscalls são implementadas em GNU assembly. O link usa
`-nostdlib -no-pie`; não existe runtime padrão nem dependência dinâmica de
Python.

### Relação entre ABIs

A ABI lógica continua sendo a assinatura tipada do S3 Assembly. System V é
somente seu transporte no target atual. Arrays e objetos de memória não são
parâmetros da linguagem e nunca atravessam chamadas. Outro target pode adotar
ABI física diferente sem mudar o S3 Assembly.

## Consequências e limites

O código é intencionalmente conservador: cada valor virtual vai ao frame e
registradores x86-64 são temporários. O compilador continua Python, mas o ELF
gerado não o contém nem o invoca. O target é exclusivamente Linux x86-64 ELF;
Windows, macOS, ARM64, libc, C, LLVM, JIT, heap e interoperabilidade externa
permanecem fora do marco.

Os limites de instruções e profundidade do emulador são proteções do
interpretador, não semântica do executável nativo. A cota estática de memória
lógica, checks de valores, bounds, inicialização e imutabilidade são
preservados.
