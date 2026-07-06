# Marco 0.8: Medição e desempenho orientado por evidências

## Estado

E0, E1 e E2 estão concluídas e integradas. A E2 foi incorporada pelo PR #4,
com o baseline determinístico oficial e a CI pós-merge validados. A E3 está
formalmente aberta para especificar a medição da CLI completa e da execução
isolada de ELF Linux x86-64, mas sua implementação ainda não começou. E4 e E5
não foram iniciadas. Nenhuma otimização estrutural de linguagem no S3 foi
criada, e a versão 0.8.0 ainda não se encontra definida, versionada ou com meta
de publicação engatilhada. O repositório segue na distribuição publicável
0.7.0.

## Motivação

Durante a homologação experimental do Marco 0.7, a instrumentação e execução apontou (via *PowerShell Measure-Command* na CLI do host) valores que reportavam aproximações exploratórias variando entre 430 ms e 503 ms até mesmo para a leitura de fontes mínimas absolutas da linguagem S3.

Entretanto, esses resultados em nenhum momento representam um benchmark oficial validado por dados empíricos isolados do core. Toda a amostragem provém do enviesado custo massivo do *startup* do interpretador, carregamento da árvore de pacotes do Python, parsing integral no sistema de arquivos nativo Windows, etc.

Adicionalmente:
- A execução através da *native-asm* emite exclusivamente as transcrições textuais sem que a ferramenta promova e integre a real cronometragem operacional dos ciclos ativados na rodada estrita ao binário (ELF final).
- Em alguns ensaios rápidos, os níveis de controle local de O1 apresentaram flutuações e métricas com resultados mistos não concretos no ganho percentual total (variando entre perda sistêmica e paridade no processamento absoluto CLI, frente ao O0 natural).
- Nenhuma execução empacotada ELF foi atrelada e aferida até agora sob as estatísticas brutas da linguagem sem intermédio interpretado.

O Marco 0.8 passa a existir inteiramente dedicado a criar métricas sólidas e ferramentas locais fidedignas para destituir inferências precipitadas, e substituí-las por medições matemáticas rigorosas e com isolamento preciso do software.

## Objetivo

Construir uma infraestrutura reproduzível, auditável e padronizada de medição sistêmica e utilizar rigorosamente os dados matemáticos extraídos dessa ferramenta própria para selecionar apenas uma única e clara melhoria de desempenho, comprovada estritamente pelas evidências colhidas, sem retroceder o comportamento determinístico das outras instruções ou quebrar a solidez aprovada da sintaxe e artefatos em uso.

## Escopo incluído

O contrato final estipulado e aprovado na [ADR-0015](decisions/ADR-0015-performance-measurement-and-benchmarking.md) abrange e limita o esforço a:
- Estabelecimento oficial normativo e irrefutável do contrato métrico.
- Codificação futura restrita de workloads oficiais rastreados em fonte e assertividade algorítmica.
- Criação integral de um runner Python injetado e projetado in-process no projeto (para divisão do emulador hospedado sem peso CLI nativo de sub-threads iterativas isoladas de O.S.).
- Emissão obrigatória da captura matemática consolidada em JSON formatado de acordo com requisitos rígidos, estáveis e padronizados no ADR.
- Métricas captadas minunciosamente divididas por cada fase acionável na construção e virtualização da chamada (Token, IR, Semantic, Emissão).
- Acompanhamento passivo atrelado das contagens determinísticas intrínsecas ao output (contagem instrucional estática e bytes brutos ELF ou .s).
- Disparo de medições *end-to-end* da CLI e chamadas atreladas isoladamente.
- Ciclo de execução real sobre artefatos ELF previamente construídos e
  validados, sem recompilar dentro do loop de amostragem.
- Geração de relatório conclusivo apontando o veredito empírico da performance O0 frente à otimização O1 em cada bloco aferido, para atestar os limites e falhas atuais das engrenagens lógicas da linguagem e das fases compiladoras (diagnóstico de gargalo).
- Adoção finalíssima estrita a uma única otimização focada, implementada tão logo e meramente com a confirmação diagnóstica pautada em dados.

## Fora do escopo

Toda e qualquer interferência não orientada por este objetivo isolado da E0 continua retida do escopo MVP e Pós-MVP do projeto:
- Interpretação dinâmica JIT ou alocações automatizadas ativas via Garbage Collection (GC).
- Adoção de novos tipos no core ternário ou modificações nos lexers em favor de sintaxes e opcodes desconhecidos.
- Desenvolvimento ou pesquisa especulativa de alvos base para backend paralelo divergente de x86-64 (ARM64, Windows Binário MSVC nativo ou transpiler nativo OSX nativo, etc.).
- Construção de módulos internos de indexação e caching duradouro no projeto/ferramenta (Cache persistente S3).
- Modelagem de implementações ou modificações voltadas ao paralelismo na runtime base e multithreading do virtual loop de emulação do S3.
- Relatórios ou execuções geradoras de marketing especulativo com promoções pautadas pela competitividade externa em face de Rust/C/Go, alheios do sistema equivalente exato de testes de terceiros e de pareamento sem startup similar.
- Engajamento aleatório sistêmico englobando múltiplas otimizações disjuntas, avulsas ou predatórias a todo e qualquer código hospedado python sem aprovação ADR para o gargalo diagnosticado real.
- Modificação abrupta prematura de bump de versões da IR e distribuição S3 subjacentes do controle global.

## Contratos preservados

- A distribuição continua operando intacta sob a versão `0.7.0` durante o desenvolvimento natural deste ciclo até seu encerramento.
- A versão fonte compilada permanece intacta em sintaxe `0.6`.
- A geração da IR em JSON é obrigatoriamente preservada inalterável na compatibilidade estrita `0.5.0`.
- O target backend do Assembly gerado mantém o layout determinístico consolidado `0.5.0`.
- O Diagnostic de saída da IDE textual (e json cli) prevalece inalterado formatado no schema v`1.0.0`.
- A seleção para a sintaxe legada V0.5 impõe estritamente o parâmetro formalizador via `--source-syntax 0.5`.
- Regras normativas de restrição de automação continuam ativas: sem modo *fallback* invisível, exclusão de *autodetecção* arbitrária ou duplas sondagens (segunda tentativa) do frontend e lexer nas sintaxes preteridas.
- Apenas a host-target do ecossistema Linux suportará o ambiente real executável do ELF nativo nativo de 64 bits.

## Entregas propostas

O avanço e a estabilização funcional da base serão escalonados metodicamente via:

### E0 — Contrato normativo (concluída e integrada)
- Construção e consolidação global via ADR e Documento do marco normativo das estratégias de benchmarking.
- Definição completa das medidas estatísticas admitidas, dos parâmetros matemáticos válidos, políticas rígidas da integração contínua (CI) e determinação das limitações estritas (escopos in e out) embutidas.

### E1 — Workloads e runner no mesmo processo (concluída e integrada)
- Planejamento e implantação oficial in-repo das métricas alvo/workloads rastreáveis que não possuam vieses temporais em dependências do relógio sistêmico, redes e interdependências.
- Confecção e injetamento lógico do utilitário core em local Python normatizado pelo repositório (ex: `tools/benchmark.py`), contendo warmups e rotinas exclusivas em memória viva.
- Inclusão plena do pipeline funcional com cálculos de média, mínima, máxima, mediana real e dispersão/p95 de O0/O1 sob o json output isolado rigoroso exigido; incluindo a exigência intrínseca que os testes sejam avaliados pelo checksum antes e nunca pautados no resultado gerado puramente em run ELF nativa remota (somente testes API in-process).

### E2 — Tempos por fase e métricas determinísticas (concluída e integrada)
- Integração da medição detalhada no runner de emulação, subdividida no percurso: leitura/tokenization do frontend, verificação de lógica semântica IR, otimizador estático passivo atrelado do Assembly até os ticks e disparos de geração do opcode nativo.
- Captação intrínseca matemática estruturada via hashes imutáveis das contagens de funções iteradas nativas e bytes emitidos estáticos textuais.
- Abstenção formal de ativações indevidas na cli interface via novas flags experimentais que não possuam ratificações independentes via decisão explícita no conselho técnico da ramificação do desenvolvimento S3.

### E3 — CLI e ELF Linux x86-64 (formalmente aberta, não implementada)

A abertura da E3 é normativa. A etapa coletará evidências para a análise
posterior, sem escolher gargalos ou implementar otimizações. A interpretação
dos resultados pertence à E4; qualquer otimização aprovada pertence à E5.

#### Objetivo e superfícies

A E3 medirá O0 e O1 sobre os mesmos sete workloads oficiais, preservando a
correção funcional, em duas superfícies independentes:

- `cli-end-to-end`: representa a experiência completa do usuário ao invocar um
  comando público já existente. A medição pode incluir inicialização do Python,
  parsing de argumentos, leitura de arquivos, frontend, IR, otimização,
  lowering, geração de Assembly e, quando fizer parte do comando escolhido,
  invocação da toolchain. Essa superfície não representa o tempo isolado do
  programa nativo;
- `elf-execution`: mede somente a execução de um ELF Linux x86-64 previamente
  construído e validado. Exclui da amostra o build, a toolchain e a
  inicialização da CLI hospedada.

Os tempos dessas superfícies não podem ser somados nem apresentados como uma
única medição.

#### Matriz de execução

O desenho deve compor independentemente:

```text
workload × optimization × surface × purpose
```

As dimensões iniciais são:

- workload: os sete casos do manifesto oficial;
- optimization: O0 ou O1, pelo mesmo caminho estrutural, variando somente o
  nível solicitado;
- surface: `cli-end-to-end` ou `elf-execution`;
- purpose: validação funcional ou medição temporal.

Por exemplo:

```text
arrays × O1 × elf-execution × measurement
recursion × O0 × cli-end-to-end × validation
```

Não haverá executor, estatística, serializer ou formato especial por workload.
Adicionar futuramente um oitavo workload deverá exigir somente uma entrada no
manifesto ou na fonte de casos, sem mudanças nesses componentes.

#### Princípio de ortogonalidade

> Compilar, executar, validar, medir, calcular estatísticas e serializar
> resultados são responsabilidades distintas. Uma alteração em uma dessas
> responsabilidades não deve exigir mudanças desnecessárias nas demais.

Esse princípio impõe as seguintes fronteiras:

- build e execução: o builder recebe workload e configuração e produz um
  artefato validável; o executor recebe um artefato já produzido e devolve o
  resultado da execução;
- execução e validação: o resultado de processo distingue status, retorno
  esperado e observado, stdout, stderr, timeout e duração. O executor não
  decide sozinho se a amostra é estatisticamente admissível;
- validação e estatística: o validador rejeita falhas funcionais antes do
  cálculo; o componente estatístico recebe somente durações já validadas;
- estatística e serialização: minimum, maximum, mean, median e p95 são
  calculados sem decidir nomes de campos, ordenação, apresentação, escrita em
  disco ou política de baseline;
- benchmark e CLI pública: a ferramenta de benchmark deve preferir as
  interfaces públicas existentes e não pode adicionar flags experimentais à
  CLI por conveniência. Uma mudança pública futura exigirá necessidade,
  justificativa, compatibilidade e testes próprios;
- medição e otimização: a E3 não altera lowering, seleção de instruções,
  alocação de registradores, geração x86-64, O0 ou O1. Evidências de possível
  gargalo são registradas sem solução nesta etapa.

#### Build, warmups e validade das amostras

Para `elf-execution`, a sequência obrigatória é:

```text
construir uma vez
validar o artefato
executar warmups
executar amostras medidas
calcular estatísticas
```

Cada ELF é construído antes da amostragem e nunca recompilado dentro do loop.
Warmups usam o mesmo artefato, mas não entram nas estatísticas. Uma amostra
medida somente é válida quando o processo inicia corretamente, não sofre
timeout, termina com status admissível, produz o retorno funcional esperado e
não apresenta stdout ou stderr incompatível com o contrato do caso. Amostras
inválidas são excluídas dos cálculos e fazem a validação falhar; elas não podem
ser silenciosamente descartadas.

#### Política de CI

Podem funcionar como gates determinísticos:

- produção, presença e execução do ELF;
- ausência de timeout e validade do status e do resultado funcional;
- equivalência semântica entre O0 e O1;
- execução de todos os workloads obrigatórios e zero skips no job nativo;
- validade do JSON e respeito ao formato declarado;
- estabilidade deliberada do baseline determinístico;
- presença das fases obrigatórias;
- impossibilidade de incluir amostra inválida nas estatísticas.

Duração individual, minimum, maximum, mean, median, p95, diferença percentual
entre O0 e O1, velocidade absoluta e variação do runner são exclusivamente
informativos. A CI não pode falhar porque O1 ficou uma porcentagem mais lento
nem porque uma amostra válida excedeu um limite de desempenho. Timeout é
permitido somente como proteção contra processo travado.

#### Política de dados

O baseline determinístico oficial não recebe tempos, estatísticas temporais,
warmups, runs, timestamps, commit, estado dirty, CPU, sistema operacional,
arquitetura, Python, hostname, caminhos ou metadados do GitHub Actions.
Resultados temporais e ambientais sanitizados podem existir como saída local,
artefato efêmero da CI, relatório manual, JSON não versionado ou seção
informativa do log. Caminhos privados e diretórios temporários não são
versionados.

#### Testabilidade da implementação futura

A implementação deverá permitir substituir ou injetar relógio, executor de
processos, builder de artefatos, diretório temporário, número de warmups e
número de runs. Assim, testes controlados poderão cobrir timeout, falha ao
iniciar processo, status não zero, stdout ou stderr inesperado, retorno
incorreto, amostras conhecidas, mediana, p95, exclusão de amostra inválida,
falha da toolchain e artefato ausente.

#### Fora do escopo da E3

A E3 não introduz sintaxe, opcode, IR, S3 Assembly, schema diagnóstico, nível
de otimização ou mudança de CLI pública sem decisão independente. Também não
escolhe gargalo, não implementa otimização e não inicia E4 ou E5.

### E4 — Diagnóstico de gargalo
- Levantamento documental com apuração exaustiva matemática produzida pelos números reportados no `JSON`.
- Determinação isolada analítica apontando em uníssono o ponto de atrito exato limitante das etapas da IR, Emulação O0 e Virtualização.
- Documento-proposta formal requerendo aprovação mandatória do novo refatoramento ou mecanismo de solução, abstendo previamente total desestruturação dos trechos codificados antes da autorização formal via especificação ou ADR subjacente.

### E5 — Otimização dirigida por evidência
- Injeção controlada de uma única classe estrutural corretiva ao núcleo avaliado (exclusivamente baseando-se do diagnóstico).
- Garantia de imutabilidade irrestrita de bugs ou falhas ao modelo padrão de linguagem (sintaxe mantida).
- Prova pericial matemática que afira explicitamente as disparidades estatísticas no json gerado da versão da melhoria *antes* e *depois* via evidência concreta e não especulativa.

### E6 — Fechamento
- Lapidação final baseada na estabilização plena dos módulos testados documentados.
- Oficialização global da documentação nativa incorporando as melhorias do Pós-MVP (Marco 0.8 final).
- Alteração irrestrita do *bump version* no build pyproject.toml somente após os relatórios encerrarem.
- Consecução global local seguida da tag oficial da branch e do publish da nova versão nas referências GitHub da comunidade com notas finais aprovadas.

## Critérios de aceitação do Marco

1. Metodologia normativa oficializada estrita e irrestritamente aderida por nova ADR oficial.
2. CLI integracional do host, APIs Python de mesma base (in-process), geração build nativo em arquivos `.s` (assembly) e chamadas operacionais ELF devem possuir total rastreabilidade subdividida de dados informados nas medidas.
3. As assinaturas produzidas com a operação temporal nos Workloads documentados garantem perenidade (resultados determinísticos precisos, livre de anomalias flutuantes ao serem executadas fora das áreas temporizadas).
4. Rotinas de compilação ativadas por `-O0` e `-O1` demonstram imutabilidade irrestrita e não degenerada aos resultados obtidos da base semântica (integridade funcional da AST persistente aprovada sem perda algorítmica).
5. Relatórios temporais efêmeros usam JSON estrito com estatísticas e metadados
   sanitizados necessários à interpretação; o baseline determinístico
   versionado permanece livre de tempos e dados ambientais.
6. Execução final interativa ao host ELF restringe-se estritamente ao artefato sendo gerado única vez (compilado unicamente) repetido sequencial e repetitivamente de modo contido às medidas, livre do ruído compilação.
7. Variações sensíveis de processamento instável natural do agendador base (`sys-clock noise`) estão exauridas do processo de decisão rigorosa em bloqueio ou travamento contínuo das etapas de testes da plataforma paralela integrada de CI na cloud.
8. Flutuações críticas em *gates estruturais* puramente métricas físicas (contagem total atestada da pipeline binária nativa nas assembly em instruções S3 geradas ou executadas) configuram e disparam falhas determinísticas absolutas que intercedem o pull automático no host da pipeline (CI Gate).
9. Modificações orgânicas especulativas na AST, interpretador Python ou backend nativo Linux estão barradas e congeladas no escopo sem que primeiro o utilitário métrico identifique o atrito em diagnóstico documental comprobatório assinado.
10. Aceitação oficial de nova diretriz funcional corretiva se valerá de comparações analíticas pareadas diretas do sistema atual (relatório regressão inalterado temporal-físico vs melhoria contínua empírica injetada).
11. Versões de dependências (Formato texto JSON `s3ir`, assembly output `S3Asm 0.5` textual ou regras semânticas gramaticais e esquema do Diag base do `diagnostic 1.0.0`) continuarão enraizadas em imutabilidade preservada durante e ao fim deste ciclo completo, salvo emissão sub-autorizada paralela de desvio e controle do escopo Pós-MVP.
12. Sintaxe legada de retrocompatibilidade do emulador de versões prévias e de uso defasado (V0.5) continua exigindo repasse explícito, rejeitando parser paralelo invisível falho nativamente, em todas as suítes temporizadas operadas futuramente no emulador de compatibilidade do benchmark.
13. Repasses ignorados forçados de `skips` perante testes cruciais e testes limitadores das barreiras físicas executadas da pipeline obrigatória atrelada na integração x86-64 nativo Linux ficam estritamente inadmissíveis para a pipeline CI geral.

## Riscos

- Ruídos voláteis paralelos de hardware provindos da própria máquina da operação (Ex: instabilidades intrínsecas ao timer tick e do kernel sched).
- Contaminações ambientais extremas via variação elétrica (*thermal throttling* e decaimentos no scaling ativo do Governor de clock) alterando diretamente picos estatísticos ao executar testes persistentes demorados na máquina testadora.
- Gargalos falsos injetados e atritos na interceptação de file-system impostos pela intrusão invasiva dos antivírus padrões ativos hospedados do OS, alinhados com o tracking e leitura bloqueante persistente no loop contínuo gerado pelo driver do repositório *OneDrive*, deturpando tempo absoluto.
- Poluição gerada na concorrência assíncrona agressiva natural existente em clouds e CI runners abertas partilhadas em hipervisores remotos no host alheio (*Noisy neighbors* em Actions do Github em VM baseadas em multi-tenant isoladas não previsíveis).
- Indução ao marketing e avaliações pautadas puramente sobre a base matemática distorcida (microbenchmarks rasos que simulam percursos falsos irretocáveis na rotina da pipeline algorítmica).
- Rotinas e blocos de loop *warmup* excessivamente curtos ou ínfimos para condicionar o JIT interno global inicial hospedado em CPython, entregando médias viciadas por falha de caching de preaquecimento natural (Cold starts perenes não resolvidos de leitura/syscall).
- Reatividade natural inerente às fases subsequentes na implementação onde o O1 (Folding, simplificador condicional estático das expressões em compilação, ou passiva *dead-code elimination* posterior futura atrelada) omita deliberadamente blocos operantes chaves do microteste, gerando latências superestimadas irreais irreproduzíveis na análise de velocidade entre duas vertentes O0 vs O1.
- Contraste distorcido causado na avaliação direta por disparidades reais e atritos sistêmicos impostos indiretamente na rotina O0 para O1 no loop gerador estático semântico.
- Limitação artificial e acionamento excessivamente reduzido do `max_instructions` do marco pretérito forçando instabilidade acidental ao cortar iterações contínuas prematuramente (impedimento indireto provindo no processamento O0, ou diferenças relativas com o pipeline modificado).
- Expansão indesejável exagerada nos ciclos base na aprovação final do build via integração de Actions remotas (GitHub CI timeout delays paralelos aos runs da suíte por excesso temporal) acarretando gasto financeiro elevado indesejado ou tempos mortos enormes com acúmulos por pull request.
- Transbordamento e interceptação indevida passiva de serialização JSON de log exportado global englobando atalhos nativos locais das strings não estáticas confidenciais nativas das pastas e perfis das sessões locais (informação sensível hospedada indevidamente) do executor Windows remoto.
- Superotimização perigosa isolada focada somente para desviar estritamente de limites temporais curtos para uma única *carga isolada* sem representar uma melhora condicional em códigos orgânicos em S3 reais ou amplos (*overfitting* lógico focado artificial).

## Questões resolvidas na E0

**Qual camada mede o quê?**
A [Camada A] abrange o custo do software e pipeline `end-to-end` na CLI percebido pelo acionamento do script completo. A [Camada B] divide minuciosamente os componentes lógicos das instâncias Python separadas (Frontend, Semântica, IR, Virtual Emulator). A [Camada C] incide sobre o isolamento real temporário de custo do utilitário gerador e invocação estrita da GNU compiler na emissão final paralela (tempo build). A [Camada D] circunda e extrai os puros bytes executados na fase Linux após o preparo isolado e contido do O0 ou O1 compilado iterado massivamente.

**Qual relógio usar?**
O time counter global atrelado é o relógio imutável de precisão matemática estática na virtualização: `time.perf_counter_ns()`, livre do viés randômico oscilatório pernicioso dos datetimes globais locais ou de internet paralelos do SO base, medindo diretamente *nanossegundos*.

**Qual estatística é principal?**
A *Mediana* estatística matemática, responsável única em apurar e ignorar com maior resiliência todos os sobressaltos efêmeros não orgânicos inerentes (pontos fora da curva) aos processos globais instáveis.

**Como calcular p95?**
Aplicando estaticamente sem bibliotecas externas: a disposição ordenada paralela ascendente contendo $N$ amostras registradas e determinando a coleta exata central de índice pautada matematicamente via busca isolada arredondada: $index = ceil((95 / 100) \times N) - 1$.

**Quais metadados registrar?**
Todo o contexto sistêmico determinável rastreado em pipeline (Commits, distribuições de pacotes da IR/AST/Sintaxe atestada, características matemáticas inatas às arquiteturas subjacentes, configurações acopladas ao interpretador, versões O.S, número núcleos provindos no host) devidamente livres de vazamentos intrínsecos paralelos pessoais privados, diretórios de caminhos reais paralelos (home dirs) e variáveis confidenciais atreladas na raiz *env* hospedada do desenvolvedor da máquina (limpos para a segurança das avaliações abertas contínuas do run na cloud partilhada e offline locais paralelos de verificação estrita remota do runner global base hospedado remoto local base paralela).

**O que bloqueia CI?**
Gates temporais flutuantes relativas ao cronômetro exato milissegundos hospedados local/host cloud, assim como ruídos orgânicos provindos de médias variantes, estão absolutamente **isolados e excluídos** como base limitante do pipeline estrito na integração. Todo e qualquer *gate* aceitável reside inflexivelmente na reprodutibilidade do script (retornos sem falha com as mesmas respostas validadas base determinísticas fixas da avaliação), imutabilidade de execuções perenes das métricas fixas estáticas operadas na base byte do binário (contagem nativa em bytes output e instrucionais assembly S3 acoplados) assim como JSON normatizado na sintaxe estrutural validado estritamente. Teste com erros ou ausência real e pulos indesejados nas plataformas Linux de execução imperativa do run nativo não irão aprovar a ramificação (zero skips no nativo O0 O1 sem false success silencioso nativo ignorando run-native real nativa base paralelamente estritamente remoto na validação O1 na base x86 nativa base CI hospedada).

**O que é apenas informativo?**
O montante estatístico base de medição (Mínima, Média, Máxima temporal estática contínua), dispersão e P95 isolados, cálculos relacionais isolados percentuais comparativos informativos em relação O1 versus O0 do microteste paralelo isolado, tempo relativo do executor do emulador hospedado end-to-end ou de invocação remota shell (relógio de execução de OS iterado de execuções ELF), permanecem livres no registro log contínuo como balanço apenas passivo referencial à engenharia posterior local (sem gate temporal contínuo na métrica contínua).

**Quando uma otimização pode ser aprovada?**
Pautada irreversivelmente aos desdobramentos lógicos paralelos produzidos no sumário da FASE E4 (Análise documentada apontando, sob os json coletados empíricos estritamente executados do framework isolado Python criado in-process na E1 e E2 acoplada à emissão paralela Linux na E3, a área principal de contenção estrutural limitante local ou de emulador), em conjunto a provas conclusivas das métricas antes e depois na regressão (comparativo prático da FASE E5 não destrutivo ao parser) demonstradas concretamente.

**Por que ELF deve ser medido separadamente?**
Englobar a inicialização iterativa da cli hospedada Python ou emissão estrita assíncrona geradora compilativa no GNU (native asm) polui irremediavelmente os décimos exatos isolados contíguos de run-native que transcrevem a velocidade do S3 ELF no nativo Linux OS base independente; o processo base impõe que o objeto executável S3 puro binário O0 e O1 existam precompilados base isolados da CLI no armazenamento RAM/File nativos base, correndo dezenas base de vezes sobre as diretivas estritas *exec* isoladamente do shell paralelo no marco normativo D estático paralelo normativo contínuo sem amarra Python e parsing da fase emissora da compilação e leitura base no relógio ELF paralela independente nativa paralela.

**Por que os resultados exploratórios atuais não são baseline oficial?**
Os laudos efetuados de modo rústico através do powershell interativo paralelo (Measure-Command host) agregaram integralmente um peso exaustivo paralelo do *cold startup process*, overheads remotos iterativos da leitura de parser da cli contínua do interpretador nativo, impossibilitando segmentar minimamente e auditar quais gargalos pertenciam essencialmente à VM virtual do código-fonte em análise contínua estrita do S3, do mero levantamento interativo do interpretador hospedeiro, falhando ao providenciar acuracidade aceitável em escala comparativa para um release público rigoroso futuro de melhorias prováveis.
