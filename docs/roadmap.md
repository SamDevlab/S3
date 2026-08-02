# Roadmap do S3

## Marco 0.1 — bootstrap vertical (concluído)

Tipos ternários, frontend inicial, lowering sem subtração, assembly, emulador,
CLI e testes.

## Marco 0.2 — funções e controle ternário (concluído e estabilizado)

Parâmetros, chamadas, recursão, switch exaustivo, IR em blocos, frames e origem.
Na estabilização 0.3, o exemplo normativo foi tornado executável, a EBNF foi
fatorada, a política de ciclos corrigida e CI adicionada.

## Marco 0.3 — memória e agregados mínimos (concluído)

- `mut` e atribuição explícita;
- arrays estáticos `trit`/`tryte`;
- objetos tipados locais ao frame;
- `LOAD`/`STORE`, `.memory`, `TLOAD`/`TSTORE`;
- bounds e inicialização seguros;
- memória independente em recursão;
- limite configurável de 6561 trits (`3^8`) por frame;
- CFG, alcançabilidade e dominância SSA;
- comunicação entre ramos sem `PHI`;
- compatibilidade 0.1/0.2 e CI Python 3.11–3.13.

## Marco 0.4 — backend nativo Linux x86-64 (concluído, experimental)

- representação int8/int16 e cálculos int64 sob ADR;
- layout determinístico de frames, flags e arrays locais;
- System V AMD64 com argumentos adicionais pela pilha;
- todos os opcodes S3 Assembly 0.3, sem `TSUB`;
- helpers tritwise, bounds, inicialização e imutabilidade;
- runtime `_start` sem libc, C, LLVM ou Python;
- CLI `native-asm`, `build` e `run-native`;
- corpus diferencial e todos os exemplos;
- CI nativa obrigatória em Ubuntu x86-64.

## Marco 0.5 — robustez e otimização inicial (concluído e validado)

Validado pelo GitHub Actions no commit `70d10a0`, com sucesso em:

- Python 3.11;
- Python 3.12;
- Python 3.13;
- backend nativo Linux x86-64.

Entregas validadas na execução remota acima:

- correção de entrada física no bloco `entry`;
- limite nativo configurável de frames;
- diagnósticos com função, bloco, opcode, origem e valor;
- S3 Assembly e IR JSON versionadas em 0.5.0;
- round-trip e verificação estrita de IR;
- análise conservadora de inicialização;
- O0 padrão e O1 local com verificação dupla;
- testes de ELF reproduzível na mesma toolchain;
- diferenciais O0/O1 emulador/nativo;
- estudo ARM64 sem backend ou alegação de suporte.

## Marco 0.6 — primeiro MVP publicável (concluído e validado)

Escopo concluído e validado antes da Entrega E:

- diagnósticos estruturados consumíveis por ferramentas na CLI hospedada;
- schema `s3-diagnostic` 1.0.0, com categorias e códigos estáveis;
- formato textual preservado como padrão;
- fronteira explícita: o runtime ELF continua com diagnósticos textuais.
- simplificação da sintaxe de fonte (ADR-0013):
  - Entrega A concluída e validada;
  - Entrega B concluída e validada;
  - Entrega C1 concluída e validada;
  - Entrega C2 concluída e validada;
  - Entrega D1 concluída;
  - Entrega D2A concluída;
  - Entrega D2A.1 concluída;
  - Entrega D2B concluída e validada;
  - V0.6 é o default do frontend e da CLI;
  - V0.5 continua disponível por seleção explícita, sem fallback;
  - corpus oficial migrado para V0.6.

Entrega E:

- fechamento do contrato do MVP e da versão pública 0.6.0;
- auditoria de instalação, empacotamento, CLI, exemplos e artefatos;
- notas de lançamento preparadas;
- concluída e validada no commit
  `aceee820ebc99b7d90fc5d32dd8fa8e699ad37b5`;
- GitHub Actions
  [`28737520765`](https://github.com/SamDevlab/S3/actions/runs/28737520765)
  verde em Python 3.11–3.13 e Linux x86-64 nativo;
- Marco 0.6 concluído.

## Marco 0.7 — paridade do limite de instruções (concluído)

A E0 aprovou o contrato normativo do limite de instruções. A E1 implementou
a paridade hospedada. A E2 implementou a instrumentação nativa. O contrato está no
[ADR-0014](decisions/ADR-0014-hosted-and-native-instruction-limit.md) e no
[plano do marco](milestone-0.7.md).

Estado:

- E0, decisão normativa: concluída;
- E1, paridade hospedada e interface pública: concluída;
- E2, instrumentação nativa: concluída;
- E3, validação ELF: concluída;
- E4, fechamento: concluída; versão 0.7.0, tag e release publicadas.

O que a E1, E2 e E3 entregaram:

- `DEFAULT_MAX_INSTRUCTIONS = 100_000` como constante pública em `emulator.py`;
- `max_instructions` exposto em `run_source`, `execute_assembly` e `generate_native_assembly`;
- `s3 run`, `native-asm`, `build` e `run-native` aceitando `--max-instructions N` com validação de valores inválidos;
- contador de instruções e falhas estruturadas instrumentadas no backend x86-64;
- diagnóstico `S3E_RUNTIME_INSTRUCTION_LIMIT` hospedado preservado sem alteração;
- validação ELF real O0/O1, controle de fluxo e chamadas, e preservação da faixa u64 nativa.

O default aprovado é `100000` opcodes S3 Assembly executados. Fonte, gramática,
AST, semântica, IR 0.5.0, Assembly 0.5.0 e schema diagnóstico 1.0.0 não mudam.
Nenhuma outra funcionalidade foi incorporada.

## Marco 0.8 — Medição e desempenho orientado por evidências

O Marco 0.8 foi iniciado exclusivamente em nível normativo. A infraestrutura de benchmark, medição estruturada de O0/O1 e execução paralela do ELF visam embasar dados empíricos precisos antes de implementar qualquer otimização adicional na base semântica da linguagem S3.

Estado atual:

- E0, contrato normativo: concluída e integrada;
- E1, workloads e runner no mesmo processo: concluída e integrada;
- E2, tempos por fase e métricas determinísticas: implementada no Draft PR #4, aguardando revisão e integração;
- E3, CLI e ELF Linux x86-64: futura;
- E4, diagnóstico de gargalo: futura;
- E5, otimização dirigida por evidência: futura;
- E6, fechamento (sem versão 0.8.0 publicada ainda): futura.

Nenhum outro benchmark ou otimização foi implementado ainda.

## Pós-MVP / marcos futuros

Não integram o Marco 0.7 e não estão implementados:

1. cache de artefatos por conteúdo/versionamento;
2. métricas e orçamento de otimização por exemplo;
3. otimizações entre blocos provadas sem `PHI`;
4. backend ou execução ARM64 experimental.

Arrays em assinaturas, heap, ponteiros públicos, strings dinâmicas e I/O
continuam fora do MVP até receberem contratos próprios. Módulos e imports
determinísticos foram entregues no Marco 0.99. O Marco 0.53 cobre
valores `string` estáticos tipados, e o Marco 0.54 adiciona concatenação
estática literal-only em tempo de compilação. O Marco 0.55 estende `len(...)`
para calcular comprimento de texto estático em tempo de compilação. O Marco
0.56 adiciona igualdade e desigualdade de texto estático em tempo de
compilação. O Marco 0.57 permite propagar texto estático por bindings
imutáveis locais. O Marco 0.58 adiciona indexação de texto estático em tempo
de compilação com índices literais. O Marco 0.59 adiciona slicing e consultas
de texto estático em tempo de compilação. O Marco 0.60 adiciona propagação de
constantes escalares imutáveis e folding de expressões constantes para alimentar
índices e bounds estáticos. O Marco 0.61 consolida constantes escalares e texto
estático em um avaliador semântico unificado e especifica transformações de
texto estático em tempo de compilação.

## Marco 0.97 - Differential Correctness Matrix

O Marco 0.97 adiciona uma matriz diferencial interna para validar equivalencia
entre emulador O0, emulador O1, ELF Linux x86-64 O0 e ELF Linux x86-64 O1.

Entregas:

- harness interno table-driven em `tests/support/differential.py`;
- corpus hospedado cobrindo tipos ternarios, operacoes, controle, chamadas,
  recursao, memoria, erros e formas SSA/de-SSA;
- inventario testado dos passes O1 ativos, com `cse` mantido fora do pipeline;
- probes estruturais e telemetria por passe quando disponivel;
- 12 casos nativos de sucesso e 4 casos nativos de erro no job
  `native-x86-64`;
- regressao SCCP corrigida para preservar o contrato de `TRET` em funcoes que
  O1 prova como nao retornantes.

Nao houve mudanca de sintaxe publica, formatos estaveis, ABI, CLI, goldens,
baselines ou versao publica.

## Marco 0.98 - Optimizer Architecture

O Marco 0.98 torna a arquitetura interna do otimizador O1 explicita sem alterar
semantica da linguagem, formatos publicos, ABI, CLI, goldens, baselines ou
versao publica.

Entregas:

- `bootstrap.s3.ssa_opt` preservado como fachada de compatibilidade;
- passes SSA separados em `bootstrap.s3.ssa_optimizer` por responsabilidade;
- contratos de passes e inventario O1 mantidos em uma unica fonte interna;
- `PassResult` usado pela pipeline para padronizar funcao transformada,
  mudanca estrutural e telemetria;
- convergencia ainda definida por diferenca estrutural real na SSA retornada,
  conforme [ADR-0016](decisions/ADR-0016-ssa-optimization-correctness.md);
- limites de modulo documentados em
  [ADR-0017](decisions/ADR-0017-ssa-optimizer-module-boundaries.md) e no
  [plano do marco](milestone-0.98.md).

Nao houve novo passe de otimizacao, sintaxe publica, SSA publica, modulo/import
de linguagem, records, enums ou componente autohospedado.

## Marco 0.99 - Modules and Imports

O Marco 0.99 adiciona compilacao deterministica de multiplos arquivos, mantendo
compatibilidade com programas de arquivo unico e sem introduzir package manager.

Entregas:

- sintaxe opcional `module`, `from ... import ...`, alias com `as` e
  `export fn`;
- graph deterministico com `ModuleId`, `SourceUnit`, `ImportEdge` e
  ordenacao topologica;
- diagnosticos para modulo duplicado, modulo ausente, ciclos, imports
  duplicados, conflitos, simbolos privados e simbolos ausentes;
- resolucao por namespace de modulo com funcoes privadas por default;
- API `compile_sources(...)` separada de `compile_source(...)`;
- nomes internos deterministicos para linking dentro do compilador, preservando
  `main` no modulo de entrada;
- cobertura hospedada O0/O1 e cobertura nativa multi-modulo no job
  `native-x86-64`;
- contrato documentado em [spec/modules.md](../spec/modules.md) e no
  [plano do marco](milestone-0.99.md).

Nao houve wildcard import, qualified calls, package manager, registry,
download de dependencias, formato publico de linking, alteracao de ABI ou bump
de versao publica.

## Marco 1.00 - Records and Enums

O Marco 1.00 adiciona tipos compostos nominais minimos para programas S3
maiores, sem alterar formatos publicos, CLI, goldens, baselines ou versao
publica.

Entregas:

- sintaxe `record` com campos nomeados em ordem declarada;
- sintaxe `enum` com variants fechadas e discriminants `tryte`
  deterministicos iniciando em `0`;
- construcao de records por campos nomeados e acesso por `valor.campo`;
- construcao de enums por `Enum.Variant`;
- comparacao nominal de enums com `==` e `!=`;
- `match` exaustivo sobre enum, com fallback `else` permitido;
- diagnosticos estaveis para tipos duplicados, campos duplicados, campos
  ausentes/desconhecidos, variants duplicadas/desconhecidas e match enum
  incompleto/duplicado;
- lowering deterministico de records por scalarizacao em ordem declarada;
- parametros record expandidos no ABI interno de IR;
- retorno de record single-field pelo registrador escalar existente;
- retorno de record multi-field bloqueado ate uma ABI de retorno agregado;
- nomes de tipos compostos module-local preservados em `compile_sources(...)`
  por reescrita interna deterministica;
- cobertura hospedada O0/O1 e cobertura nativa x86-64 para records/enums.

Nao houve classes, metodos, heranca, traits, interfaces, generics, reflection,
enum payloads, heap, layout aberto, novo opcode, formato publico novo ou bump
de versao publica.

Contrato documentado em [spec/composite-types.md](../spec/composite-types.md) e
no [plano do marco](milestone-1.00.md).

## Marco 1.01 - First Self-hosting Component

O Marco 1.01 implementa o primeiro componente pequeno do toolchain escrito em
S3 e validado contra uma referencia Python, sem substituir o caminho padrao do
compilador.

Componente escolhido:

- classificador de opcodes de S3 Assembly;
- subcomponente estreito do futuro renderer de Assembly;
- referencia Python baseada em `bootstrap/s3/assembly.py` e no inventario
  `AssemblyOpcode`.

Entregas:

- `selfhost/assembly/opcode_ids.s3` com ids escalares deterministicos para os
  opcodes atuais;
- `selfhost/assembly/opcode_classifier.s3` usando modulos, records, enums e
  `match` exaustivo;
- classificacao de opcode conhecido, kind, contagem minima de operandos,
  variadicidade de `TCALL` e aceitacao de contagem de operandos;
- teste diferencial Python/S3 cobrindo todas as variants atuais, entradas
  invalidas, comportamento variadic e determinismo de compilacao multi-file;
- checksum nativo x86-64 coletavel quando o toolchain nativo estiver
  disponivel.

Estado de maturidade: `differential reference`. O componente nao foi adotado
como caminho padrao; Python permanece a referencia.

Contrato documentado em [docs/milestone-1.01.md](milestone-1.01.md) e na
selecao em [docs/self-hosting-first-component.md](self-hosting-first-component.md).

## Marco 1.02 - Language Composition

Status: Complete

O Marco 1.02 estabiliza contratos de composicao de linguagem identificados apos
a integracao da campanha 0.97-1.01. Ele nao altera ABI, IR, Assembly, goldens,
baselines ou versao publica por si so.

### 1.02-A - Record contract alignment

Status: Complete

Resultado:

- fields suportados: `trit`, `tryte` e enum fechado;
- ainda rejeitados: nested records, records recursivos, arrays, string e
  imported records como fields;
- contrato alinhado em [spec/composite-types.md](../spec/composite-types.md) e
  no plano da [Milestone 1.02](milestone-1.02.md).

### 1.02-B - Postfix composition and qualified names

Status: Complete

Concluido:

- B1: especificacao em [spec/postfix-expressions.md](../spec/postfix-expressions.md);
- [ADR-0018](decisions/ADR-0018-postfix-qualified-resolution.md);
- gramatica normativa em [spec/grammar.ebnf](../spec/grammar.ebnf);
- contrato para diferenciar modulos, enums e record members durante a analise
  semantica;
- B2: parser postfix unificado e AST com call, index, slice e member
  encadeados;
- B3: resolucao semantica de qualified calls, qualified enum variants e labels
  qualificados de match;
- B4: contrato de record member access, diagnostics explicitos e limites de
  composicao preservados;
- B5: lowering/verifier cobrindo callee concreto, discriminants e scalarizacao
  sem opcode publico novo;
- B6: integracao diferencial hospedada O0/O1, multi-modulo e determinismo;
- B7: cobertura nativa x86-64 O0/O1 para qualified postfix execution.

Continuidade:

- 1.02-C concluiu os contratos de tipos nominais entre modulos descritos abaixo.

### 1.02-C - Cross-module nominal types

Status: Complete

Concluido:

- C1: identidade nominal especificada como `ModuleId + TypeName`;
- [ADR-0019](decisions/ADR-0019-cross-module-nominal-type-identity.md);
- contrato de `export record` e `export enum`;
- separacao normativa entre namespaces de funcoes, tipos, modules, variants,
  fields e valores;
- C2: exported nominal type symbols no grafo de modulos, com diagnosticos de
  tipos privados, ausentes e conflitantes;
- C3: imported nominal values para records e enums em variaveis, parametros,
  retornos single-field, construcao, copia, field access, variants qualificadas
  e match;
- C4: contrato de layout nominal cross-module, com field order do modulo de
  origem, discriminants por ordem declarada, incompatibilidade same-name e
  same-shape, e determinismo de source order;
- C5: cobertura diferencial O0/O1 e nativa Linux x86-64 para valores nominais
  importados;
- C6: consolidacao documental da Milestone 1.02;
- type import aliases, wildcard imports e reexports gerais mantidos fora do
  escopo;
- imported record como field continua rejeitado ate a milestone de nested
  records;
- retorno de record multi-field e retorno agregado geral continuam rejeitados
  ate existir uma ABI agregada aprovada.

## Marco 1.03 - Acyclic Nested Records

Status: Complete

O Marco 1.03 especifica e implementa nested records aciclicos e layout composto
deterministico sem alterar ABI, IR publico, Assembly publico, goldens,
baselines ou versao publica.

Concluido:

- auditoria arquitetural inicial;
- gate inicial confirmando que locals, constructors, copias, parametros e
  member access podem ser representados por scalarizacao de folhas no IR atual;
- [ADR-0020](decisions/ADR-0020-acyclic-nested-record-layout.md);
- contrato normativo em [spec/composite-types.md](../spec/composite-types.md);
- `SemanticModel.record_leaves()` como fonte canonica de paths, tipos, ordem
  depth-first/declarada, scalarizacao, copias, parametros, member access e
  classificacao de retorno;
- nested records locais de dois, tres e quatro niveis;
- records importados como fields;
- constructors qualificados e constructors nested qualificados;
- initializers fora da ordem declarada preservando layout declarado;
- determinismo multi-module e independencia de source order;
- cobertura hospedada O0/O1 e cobertura nativa Linux x86-64 para nested record
  execution.

Limites preservados:

- layouts recursivos continuam rejeitados;
- retorno de record multi-leaf continua rejeitado antes do lowering;
- nao ha hidden return pointer, retorno multi-register, offsets publicos ou
  alignment nominal.

## Marco 1.04 - Fixed-Capacity Static Text Foundation

Status: Complete

O Marco 1.04 consolida `string` como texto estatico de capacidade fixa:
conteudo conhecido em tempo de compilacao, capacidade igual ao byte length
UTF-8 decodificado, handle escalar interno, sem heap, sem buffer mutavel, sem
ponteiro publico e sem mudanca de ABI.

Concluido:

- auditoria da infraestrutura existente de static text;
- especificacao em [docs/milestone-1.04.md](milestone-1.04.md);
- preservacao de `IRType.STRING`, `IRStaticString`, `CONST_STR`, `.data`,
  `TCONST_STR`, emulador e `.rodata` nativo;
- operacoes compile-time existentes: `len`, index, slice, igualdade,
  `contains`, `starts_with`, `ends_with`, `find`, `upper`, `lower`, `trim`,
  `repeat` e `replace`;
- `string` como folha escalar em records, nested records e imported records;
- cobertura hospedada O0/O1 e harness nativo para record fields textuais.

Limites preservados:

- operacoes runtime sobre texto nao estatico continuam rejeitadas;
- `main -> string` continua rejeitado;
- arrays de string e arrays de records continuam fora;
- retorno agregado e retorno multi-leaf continuam rejeitados.

### Later language-composition milestones

Status: 1.05 and 1.06 complete locally in Draft PR #126; 1.07 started in the
aggregate-results campaign

- 1.05 - enums com payload e erros estruturados: [ADR-0021](decisions/ADR-0021-enum-payload-layout-gate.md)
  foi aceita e implementada localmente com layout fixo tag-first multi-cell,
  largura por tipo, payload scalarizado, slot types canonicos, slots inativos
  deterministicos, construcao qualificada, imports, parametros, copias,
  branches, loops, match bindings, O0/O1, harness nativo e ABI de retorno
  escalar preservada;
- 1.06 - componentes adicionais de self-hosting: seleciona o classificador de
  opcodes existente, um classificador de diagnostics e um validador de
  discriminants/layout escalar como componentes pequenos, puros e diferenciais,
  mantendo Python como referencia e default; os componentes estao classificados
  como differential references, nao como implementacoes adotadas.
- 1.07 - layouts fixos unificados: [plano da milestone](milestone-1.07.md)
  especifica um contrato semantico unico para valores fixos scalarizaveis
  (escalares, texto estatico, records e enums), mantendo os wrappers
  `record_leaves()` e `enum_layout()` como consultas derivadas.
- 1.08 - arquitetura de resultados multicelula:
  [ADR-0022](decisions/ADR-0022-aggregate-function-results.md) aceita listas
  ordenadas de result cells em IR/Assembly, versionamento 0.6.0 para novos
  writers e sret interno apenas no backend nativo quando a largura for maior
  que 1.
- A implementação da 1.08 move os writers atuais de IR/S3 Assembly para 0.6.0,
  preserva leitores 0.5 width-1, materializa grupos completos em CALL/RETURN,
  preserva SSA/O1 por construção e mantém heap, ponteiros visiveis na linguagem,
  generics, exceptions e substituicao do bootstrap Python fora do escopo.

### Out of scope after 1.04

Status: Out of scope

Arrays como record fields, recursive layouts, methods, generics, heap, dynamic
text, package manager, aggregate returns e self-hosting completo continuam fora
deste checkpoint documental.

## Autohospedagem

Assembler e frontend em S3 dependem de strings além de concatenação estática
literal-only, comprimento estático, igualdade estática, propagação por
bindings imutáveis, indexação estática de texto, slicing e consultas estáticas
de texto, propagação de constantes escalares imutáveis, folding de expressões
constantes, transformações de texto estático, módulos e uma biblioteca padrão
mínima. Python será removido gradualmente somente após bootstrap reprodutível.
