# Arquitetura do S3 bootstrap 0.4

## Pipeline

```text
fonte → lexer → AST → semântica
      → lowering SSA + objetos de memória
      → IR com CFG/dominância verificada
      → S3 Assembly tipada e validada
        ├→ emulador com frames e memória local
        └→ backend x86-64 → GNU assembly → ELF Linux
```

AST, semântica, IR e assembly permanecem modelos separados. Origem atravessa
camadas por `SourceLocation`.

## Frontend

A AST distingue tipo escalar/array, literal de array, indexação, mutabilidade e
alvos de atribuição. A tabela semântica associa a cada binding tipo,
mutabilidade, origem e condição de parâmetro.

Arrays não entram nas assinaturas nem no sistema de valores escalares. Bounds
de expressões constantes simples (`literal`, negação, soma/subtração) são
checados estaticamente; demais índices chegam ao emulador.

## Lowering híbrido

- escalar imutável: registrador SSA;
- escalar `mut`: objeto de memória de comprimento 1;
- qualquer array: objeto de memória do comprimento declarado;
- leitura: `LOAD`;
- inicialização/atribuição: `STORE`;
- índices e valores: registradores SSA.

Em switch, ramos armazenam no mesmo objeto preexistente e o join carrega o
valor. Não há `PHI`.

## CFG e dominância

O verificador valida todos os blocos, constrói arestas dos terminadores, calcula
alcançabilidade e dominadores por ponto fixo. Uma definição deve preceder o uso
no bloco ou dominar o bloco consumidor. Isso rejeita valores originados em
apenas um ramo e usados no join.

Ciclos são permitidos. A análise não prova terminação; o emulador aplica limite
global configurável de instruções.

## Assembly e memória por frame

`.memory` torna objetos autocontidos no texto. `TLOAD`/`TSTORE` não manipulam
endereços, apenas identidade de objeto e índice.

Ao criar um `Frame`, o emulador:

1. copia parâmetros para registradores;
2. aloca lista independente de células não inicializadas por objeto;
3. verifica custo contra `max_memory_trits`;
4. executa bounds, tipo e inicialização em cada acesso;
5. descarta memória ao retornar.

Defaults:

```text
max_frames        = 1024
max_instructions  = 100000
max_memory_trits  = 6561
```

## Backend nativo

`backends/x86_64` consome apenas `AssemblyProgram` validado pelo limite público
do emulador. O layout é uma etapa isolada: registradores ordenados recebem
slots de 8 bytes e flags; objetos ordenados recebem regiões int8/int16 e flags
por elemento; regiões não se sobrepõem e o frame termina alinhado a 16 bytes.

O emitter mantém todos os valores virtuais no frame e usa registradores AMD64
como temporários. Funções seguem System V: seis argumentos em registradores,
demais na pilha, retorno em `RAX`. O runtime assembly fornece `_start`,
conversão decimal, helpers tritwise, `write`, `exit` e falhas controladas. A
toolchain detecta Linux x86-64 e invoca `cc`/`gcc`/`clang` sem shell, com
temporários isolados.

```text
S3 lógico: trit=1 trit, tryte=6 trits, cota=6561/frame
x86-64 físico: trit=int8, tryte=int16, valores temporários=int64
```

Essas medidas são independentes: flags, padding e slots físicos não consomem a
cota lógica.

## Invariantes

1. Sem conversões implícitas ou overflow silencioso.
2. `-1` continua dois tokens.
3. Imutáveis escalares permanecem SSA.
4. Memória é local, tipada, sem aliasing e sem endereço exposto.
5. Nenhuma leitura não inicializada retorna valor.
6. Bounds nunca são silenciosos.
7. Codegen consome somente IR verificada.
8. Não existem `PHI`, `SUBTRACT`, `TSUB`, ponteiros ou casts.
9. Python continua apenas compilador bootstrap; o ELF não depende dele.
10. Emissão textual, símbolos e offsets são determinísticos.

## Riscos

Todos os objetos lexicais da função são alocados ao entrar no frame, inclusive
os de ramos não executados; é simples e conservador, mas pode superestimar
memória. Inicialização de memória imutável é verificada dinamicamente na
assembly. O layout x86-64 ainda não aloca registradores, não reproduz os limites
operacionais de instruções/frames do emulador e não possui heap, aliasing ou
promoção memória-para-SSA. Outros sistemas/arquiteturas exigem backend e ADR
próprios.
