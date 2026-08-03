# Arquitetura do S3 bootstrap 0.5

## Pipeline

```text
fonte → lexer → AST → semântica
      → lowering SSA + objetos de memória
      → IR com CFG/dominância verificada
      → análise de inicialização → otimização O0/O1 → nova verificação
      → S3 Assembly 0.6 tipada, versionada e validada
        ├→ emulador com frames e memória local
        └→ backend x86-64 → GNU assembly → ELF Linux
```

AST, semântica, IR e assembly permanecem modelos separados. Origem atravessa
camadas por `SourceLocation`.

## Frontend

A AST distingue tipo escalar/array, literal de array, indexação, mutabilidade e
alvos de atribuição. A tabela semântica associa a cada binding tipo,
mutabilidade, origem e condição de parâmetro.

Arrays fixos `trit`/`tryte` entram em assinaturas como grupos de células
derivados de `SemanticModel.fixed_value_layout(...)`. A passagem é copy-by-value
e não expõe endereços. Bounds de expressões constantes simples (`literal`,
negação, soma/subtração) são checados estaticamente; demais índices chegam ao
emulador.

## Lowering híbrido

- escalar imutável: registrador SSA;
- escalar `mut`: objeto de memória de comprimento 1;
- array local: objeto de memória do comprimento declarado;
- array em boundary: grupo escalar completo em ordem crescente de índice;
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

## Inicialização e O1

O passe de inicialização calcula ponto fixo por elemento com estados
`UNINITIALIZED`, `INITIALIZED` e `MAYBE_INITIALIZED`. Load constante
definitivamente inválido e segunda inicialização imutável comprovada são erros
estáticos. Índices dinâmicos e joins incertos mantêm checks de runtime.

O0 preserva a IR. O1 dobra/propaga constantes locais, remove resultados puros
seguros e mortos, blocos inalcançáveis e trampolins de salto. ADD potencialmente
overflow, efeitos e terminadores não são apagados. Verificador e análise rodam
antes e depois.

## Arquitetura interna do otimizador SSA

O otimizador O1 usa SSA apenas como representacao interna. A fachada historica
`bootstrap.s3.ssa_opt` permanece estavel para o compilador e testes existentes,
mas as responsabilidades internas ficam separadas em `bootstrap.s3.ssa_optimizer`.

Os limites atuais sao:

- `contracts.py`: contratos, inventario O1 e `PassResult`;
- `common.py`: helpers compartilhados;
- `lowering.py`: SSA para IR e CFG reconstruido de blocos SSA;
- `propagation.py`: propagacao de constantes e copias;
- `value_numbering.py`: CSE e GVN;
- `elimination.py`: DCE, ADCE e DSE;
- `loops.py`: LICM e strength reduction;
- `sccp.py`: propagacao condicional esparsa;
- `peephole.py`: reescritas locais.

A convergencia do fixpoint continua baseada em mudanca estrutural real na SSA
retornada. Contadores alimentam telemetria, mas nao sao prova de convergencia
nem autorizam transformacoes que a estrutura retornada nao realizou.

## Artefatos

S3 Assembly usa `.s3asm 0.6.0`; texto legado 0.5 width-1 é normalizado. IR
persistente usa JSON `s3-ir` 0.6.0 canônica, estrita e terminada por newline.
Desserialização reconstrói modelos explícitos, normaliza artefatos 0.5 width-1
para `result_types`/`results` explícitos e chama `verify_ir`.

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

## Limite de instruções do Marco 0.7

O [ADR-0014](decisions/ADR-0014-hosted-and-native-instruction-limit.md) estendeu e implementou o
default `max_instructions = 100000` ao runtime Linux x86-64, atingindo paridade no Marco 0.7.

Cada opcode S3 Assembly efetivamente executado consumirá uma unidade. Antes do
opcode, o runtime verificará o limite, incrementará o contador uma vez e só
então executará o opcode. O contador será global para a execução, compartilhado
por chamadas e recursão e independente de frames e memória lógica. Instruções
x86-64, helpers, checks, prólogos, epílogos e syscalls não serão contados.

O orçamento incidirá sobre o S3 Assembly posterior a O0 ou O1. Limites baixos
podem terminar em pontos diferentes; execuções que terminarem dentro do
orçamento continuarão semanticamente equivalentes.

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

Toda função incrementa um contador privado antes de alocar stack e falha ao
exceder `max_frames`; cada `TRET` decrementa. Após o prólogo há salto explícito
para `entry`, independente da ordem física. Pontos de falha recebem IDs
determinísticos e strings com categoria, função, bloco, opcode e origem;
índices e resultados são impressos dinamicamente sem libc.

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
11. O0 é padrão; O1 não remove falhas semânticas observáveis. O orçamento de
    instruções incide sobre o Assembly resultante, conforme o ADR-0014.
12. Artefatos desconhecidos são rejeitados, nunca adivinhados.

## Riscos

Todos os objetos lexicais da função são alocados ao entrar no frame, inclusive
os de ramos não executados; é simples e conservador, mas pode superestimar
memória. Inicialização de memória imutável é verificada dinamicamente na
assembly. O layout x86-64 ainda não aloca registradores. O limite de frames e
o limite de instruções (implementado no Marco 0.7) são verificados ativamente no runtime.
A futura infraestrutura de medição do Marco 0.8 analisará gargalos precisos por
trás desse pipeline antes que ele sofra grandes refatoramentos de otimização.
Não há heap, aliasing ou promoção memória-para-SSA. Reprodutibilidade binária
vale somente na mesma toolchain. Outros targets exigem backend/ADR próprios.
