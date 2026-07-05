# ADR-0015: Medição de desempenho e benchmarks reproduzíveis

**Status:** Accepted

## 1. Contexto

A linguagem S3 possui execução hospedada (emulador) e execução nativa (Linux x86-64). Benchmarks exploratórios via CLI indicaram que o tempo de execução foi totalmente dominado pelo custo de startup (criação do processo, imports, parsing e leitura de arquivo). Além disso, a emissão via `native-asm` não equivale à execução do ELF gerado.

Runtimes e toolchains maduros (C, Rust, Go, Python, etc.) não podem ser comparados validamente sem uma metodologia rigorosa e equivalente. Otimizações implementadas sem medição isolada podem melhorar um microcaso específico, mas piorar o desempenho do sistema completo.

*Nota:* Os valores exploratórios iniciais reportados na E0 do Marco 0.8 são não normativos, dependentes de máquina, não comparáveis entre ambientes e inadequados como gate de CI.

## 2. Decisão

Formaliza-se a separação do desempenho em quatro camadas independentes de medição, isolando o custo de inicialização do custo real de processamento e execução.

### Camada A — CLI end-to-end

Mede:
- criação do processo;
- importação do pacote;
- parsing da CLI;
- leitura do arquivo;
- compilação;
- execução ou emissão.

Finalidade: Medir a experiência percebida pelo usuário, o custo de startup e a integração com o shell. Cada repetição deve iniciar um novo processo.

### Camada B — APIs no mesmo processo

Mede separadamente:
- frontend;
- análise semântica;
- geração de IR;
- O0/O1;
- geração de S3 Assembly;
- emulação;
- emissão x86-64.

Nesta camada, o pacote é importado uma vez, e devem existir *warmups* (aquecimentos) antes das amostras registradas.

### Camada C — Build nativo

Mede separadamente:
- frontend;
- otimização;
- emissão x86-64;
- assembler;
- linker;
- tempo total de build;
- tamanho do ELF.

Essa camada visa isolar o processo de compilação sem misturar o *build* com a execução do ELF gerado.

### Camada D — Execução ELF

Fluxo normativo:
- compilar uma vez;
- validar resultado;
- executar o mesmo ELF várias vezes;
- medir somente execução;
- medir O0 e O1 separadamente.

A execução de arquivos ELF é obrigatoriamente Linux x86-64 enquanto este for o único backend suportado.

## 3. Terminologia

- **workload:** Programa fonte específico focado em exercitar uma característica ou conjunto de características do runtime.
- **caso:** Configuração específica para executar um workload (ex: hospedado O0, nativo O1).
- **amostra:** Resultado de uma única execução cronometrada.
- **warmup:** Execução inicial descartada, útil para aquecer caches de CPU, disco e JIT do interpretador hospedeiro.
- **repetição:** Cada iteração medida.
- **mediana:** O valor central que separa a metade maior da metade menor das amostras cronometradas.
- **média:** A soma de todas as amostras dividida pela quantidade de execuções.
- **mínimo:** A amostra com o menor tempo ou custo.
- **máximo:** A amostra com o maior tempo ou custo.
- **p95:** O 95º percentil. Indica que 95% das amostras foram mais rápidas que esse valor.
- **desvio:** Dispersão (desvio padrão) das amostras ao redor da média.
- **baseline:** Conjunto de resultados considerados a base normativa para comparação.
- **regressão:** Degradação documentada de desempenho em relação ao baseline.
- **ruído:** Variações inerentes ao ambiente (como agendamento de SO).
- **gate:** Um teste cuja falha interrompe a integração contínua (CI).
- **métrica informativa:** Valores acompanhados apenas para análise, cujas variações isoladas não falham o processo de integração contínua.
- **correção funcional:** Garantia de que a otimização ou alteração preservou o comportamento esperado.
- **checksum ou resultado esperado:** Verificação determinística da saída ou efeito do programa para provar que a execução ocorreu corretamente e não foi pulada/otimizada indevidamente.

## 4. Relógio

As medições internas em Python devem obrigatoriamente utilizar um relógio monotônico de alta resolução. A função normativa escolhida é:
`time.perf_counter_ns()`

- Os valores brutos devem ser armazenados e processados internamente em nanossegundos.
- A conversão para milissegundos, microssegundos, etc., ocorrerá exclusivamente na apresentação/renderização visual dos resultados.
- A função temporal `datetime` não deve ser utilizada para medir durações devido a vulnerabilidades relacionadas ao relógio de parede.

## 5. Estatísticas mínimas

Cada resultado de benchmark deve registrar:
- warmups;
- runs;
- amostras brutas ou opção para preservá-las;
- mínimo;
- máximo;
- média;
- mediana;
- p95;
- unidade;
- resultado funcional;
- status.

A **mediana** é a métrica temporal principal. A média, o mínimo, o máximo e o p95 figuram como estatísticas complementares. 

### Cálculo do p95
Para calcular o percentil 95 de forma determinística e evitar divergências de implantação de bibliotecas, estipula-se o método *nearest-rank* (posição mais próxima arredondada para cima): as amostras em nanossegundos são ordenadas ascendentemente, a posição é encontrada através de `index = ceil((95 / 100) * N) - 1`, e a amostra nessa posição é declarada como o p95. 

## 6. Ordem e isolamento

Para mitigar viés e instabilidade de *caching*:
- Cada caso isolado deve executar e concluir seu próprio aquecimento (warmup).
- As camadas de O0 e O1 devem necessariamente competir sob as mesmas entradas rigorosas de fonte.
- Todos os resultados devem possuir a correção funcional atestada *antes* de iniciarem o contador da medição.
- A ordem de execução dos casos deve estar detalhadamente registrada. Se o runner decidir aleatorizar as execuções, o *seed* dessa aleatorização obrigatoriamente fará parte do registro.
- Diretórios temporários (tempdirs) do build e emissão devem figurar totalmente desacoplados do repositório/checkout do projeto, prevenindo rastreamento indevido pelo controle de versão.
- A saída padrão (stdout/stderr) dos programas no processo cronometrado deve ser interceptada ou suprimida, exceto se essa mesma saída for fundamental à carga de trabalho sendo medida.
- Preparos de ambientes ou mocks nas entradas não podem compor a janela de tempo da execução lógica das camadas B, C e D (com exceção aceitável na Camada A, onde reflete exatamente a percepção bruta do shell).

## 7. Workloads oficiais

As futuras cargas de trabalho mínimas exigidas serão categorizadas como:
- minimal;
- arithmetic;
- branches;
- calls;
- recursion;
- arrays;
- optimizer-stress.

Um workload oficial deverá conter:
- Fonte S3 versionada.
- O resultado funcional de checksum final atestado.
- Comportamento de foco muito bem descrito.
- Contas permissivas para max_instructions e max_frames, mitigando interrupções arbitrárias nos testes em caso de regressão marginal.
- Compatibilidade intrínseca em ser processado em ambos os perfis O0 e O1.
- Completa independência e total imunidade de relógio nativo, redes externas, interações randômicas não gerenciadas e acessos a arquivos externos.

A E0 não propõe ou constrói de forma definitiva a estrutura executável, reservada para entregas subsequentes do marco.

## 8. Métricas determinísticas

Além das medidas temporais, o Marco 0.8 institui o preparo formal de acompanhamento de métricas contáveis precisas e infalíveis:
- quantidade de instruções S3 Assembly emitidas;
- quantidade de instruções S3 executadas;
- número de funções;
- número de blocos;
- quantidade de chamadas;
- profundidade máxima de frames (quando puder ser observada pela virtualização hospedada);
- tamanho textual em bytes da saída Assembly;
- tamanho bruto em bytes do x86-64 assembly e seu respectivo artefato de ligação (ELF);
- hashes unívocos dos artefatos produzidos (identificação SHA256);
- resultado funcional (exit status int).

Fica pacificado que as mensurações em tempo são inerentemente variáveis pelo ambiente do hospedeiro, mas as listadas acima formam bases excelentes e preferíveis para *gates estruturais* que validam o comportamento determinístico da evolução tecnológica. Adicionalmente, nenhuma medição futura ou contagem destas métricas dá o direito de gerar *breaking changes* nos modelos de arquivos JSON IR, Assembly textual (.s3asm) ou schema de logs JSON (Diagnostic) sem que passe por sua própria proposta ADR.

## 9. Metadados do ambiente

Qualquer emissão oficial dos relatórios em JSON registrará:
- versão do runner de benchmark;
- commit Git correspondente;
- flag representativa de repositório (suja/árvore limpa);
- distribuição atual da linguagem (S3);
- sintaxe em teste;
- versão da emissão IR;
- versão do Assembly;
- versão do esquema textual/json Diagnóstico;
- variante do interpretador Python (ex: CPython 3.11.x);
- sistema operacional do host testado;
- plataforma/arquitetura instrucional;
- detalhes físicos/nomenclatura do processador (se acessível);
- número detectado de instâncias CPUs lógicas;
- memória acessível e estendida do ecossistema;
- flag/alavanca O0, O1;
- max_instructions repassado;
- max_frames repassado;
- timestamp universal e imutável de disparo do teste (UTC);
- modo e camada alvejada de benchmark (CLI, in-process, build nativo, repetição em processo ELF);
- total de ciclos warmups alocados;
- rodadas repetidas validadas de medição.

Para prezar pela segurança absoluta dos dados e rastros digitais efêmeros da CI, está restrito que o JSON registre: nomes de sessões interativas dos usuários (usernames), tokens de identificação locais e globais, file system mappings particulares privados e extensões não efêmeras de root hostname, além de vetos integrais ao dump total da `environ` na serialização do objeto (chaves sensíveis).

## 10. Formato de saída futuro

A geração dos laudos de benchmark se adequará às políticas mínimas futuras a seguir delineadas (sem implantação no E0):

- Obrigatório texto serializado em UTF-8 nativo e não escapado sem necessidade.
- Serialização padronizada, alinhada e JSON puro e determinístico.
- Chaves do dicionário com nomeamento fixo sem dependência dinâmica aos casos de teste (Stable Keys).
- Unidade posfixa e declarada em propriedades ao lado.
- Puros floats ou ints numéricos para estatística. Interditado o escape sob strings regionais exóticas ou com separadores vírgula incondizentes.
- Bloqueio persistente e explícito à inserção serializada dos bytes de "NaN" ou notações poluidoras de "Infinity".
- Verificadores status_check/bool confirmados explicitamente (ok ou falha) nas medições captadas.
- Mensagens textuais agrupadas nas tags descritivas da classe "erro estruturado" perfeitamente decodificáveis.
- Versão isolada que rastreia puramente as mudanças do design do JSON benchmark em questão (sem amarra à linguagem S3).

## 11. Política de CI

As balizas aprovadas nesta E0 a respeito das barreiras integracionais de build contínuo são:

### Gates obrigatórios iniciais (Bloqueantes)
- Casos da camada e workloads oficiais devolvem matematicamente as assinaturas que prometeram nos gabaritos em checksum.
- Alteração da alavanca de O0 para O1 exprime absolutamente o mesmo processamento.
- Arquivos sujos isolados e artefatos .s file em repouso são adequadamente erradicados do filesystem após o fim das execuções do runner pelo hook exit apropriado.
- Os laudos em JSON produzidos superam com 100% integridade uma bateria de validação determinística estrutural de validade formatada JSON.
- Gates limitadores fixos das métricas de contagem não flutuantes (descritos no tópico 8).
- Retirada expressa dos comandos "skip" e pulos falsamente silenciados via dependências mal carregadas no host e executor remoto de job ELF nativo.
- Ausência perene de uso dos comandos arbitrários de avanço inseguro (continue-on-error, || true, etc).

### Métricas apenas informativas inicialmente (Não Bloqueantes)
- Medição e marcações absolutas relativas ao relógio (ms).
- Flutuações pontuais de medições da média, mediana e dispersão (p95).
- Cálculos gerados entre o ganho de O0 para O1 e diferenciação de avanço com o limite tolerado.
- Relógios de acionamento das fases de build nativo e invocação independente das instâncias shell do ELF iterado.

A falha por quebra de rendimento (tempo de milissegundos degradado, flutuação do hardware cloud e instabilidades efêmeras ou perdas marginais de velocidade em cenários inter-dependentes globais) encontram-se bloqueadas. Todo o critério futuro que instituir *gates* de variação temporal de velocidade irá obrigar discussões sobre os picos sistêmicos efêmeros e exigir decisão através de sua própria ADR específica.

## 12. Comparações externas

A avaliação contra compiladores de terceira parte maduros, concorrentes com as soluções nativas do S3 (Rust, C, Go e análogos scriptados) obedecerá condicionalmente as seguintes imposições:
- Emprego de um algoritmo similar e não desvirtuado no cerne algorítmico do outro sistema e sem atalhos ilegais da compilação inteligente e dead-code elimination.
- Verificação que emana exatamente a mesma validação e precisão exigida no programa de origem.
- Subdivisão de processos para impedir cronometrar simultaneamente as camadas de parsing/lexing/IR (tempo de build da linguagem X não integrará à execução binária bruta ou JIT seletiva).
- Versões dos SDK/Binários e flags específicas devidamente transparentes (Ex: -O3, -fomit-frame-pointer).
- Subprojetos via C/Rust/Go devem certificar em isolado que compilaram ao final antes que a corrida dos medidores comecem a iterar.
- A comparação sobre a hospedada interpretada de S3 obriga pareamento à linguagens sem JIT de warm-start que atuariam anomalias, focando equiparar ao equivalente operado e isolado.
- Exclusão do startup na conta se for medido runtime. Oposto verdadeiro à end-to-end do script se intencionada mediar chamadas via Shell, desde que o peso da balança I/O de chamadas print/stdout não enviese os testes onde os drivers interagem diferentemente nos TTY/PTY.
- Prevenção à declaração errática sobre superioridades algorítmicas utilizando microcasos isolados únicos que não reproduzem fidelidade na vida real do pacote final do software (marketing desleal pautado na falácia).

Não constitui encargo presente (E0) o lançamento de competidores para as runs.

## 13. Segurança e reprodutibilidade

Para blindar e promover isolamento e veracidade aos dados:
- Contadores de instâncias exaustivas do código host (limites instrucionais ou frames) não perdem validez mesmo com benchmark interativo; eles protegem instâncias.
- As integrações e medições subjacentes operacionais não manipulam e retiram de forma mascarada a flag `--max-instructions` durante suas provas repetitivas para otimizar fumaças.
- Os jobs e workloads injetados no sistema contêm cronometragens máximas toleráveis para quebra forçada na CI, impossibilitando timeouts ilimitados infinitos que corroam créditos e processamentos da pipeline de teste (Timeout).
- Os sistemas isolantes, de arquivos e saídas residuais nativas repousam temporariamente até sua erradicação definitiva fora do espaço git, coibindo lixo cruzado em outras validações locais do projeto S3 ou execuções nativas concorrentes posteriores na máquina.
- Impedimento incondicional da virtualização/geração do runtime .S e .ELF de serem despachados dentro do runner Linux sendo a plataforma base local no momento (Windows x86_64 e MacOS).
- Rejeição incontestável das medições e registros provenientes dos testes de cases (O0 ou O1) quando identificada qualquer incongruência, inconsistência matemática e assimetria funcional nas respostas de saída devolvidas no resultado ou output estipulado pelo baseline.
- Nenhuma possibilidade mecânica automática ou acidental via auto-discoverer das suítes no módulo pytest local será deixada vulnerável para engolir as cargas externas sem que a infraestrutura se certifique explicitamente que o código vem do arcabouço próprio confiável local S3 (sem trust by default com autoexecução).
- Estipulação restritiva severa de bloqueio sistêmico à chamada remota TCP/UDP na camada virtual do teste; a bateria é 100% operada estaticamente offline não dependendo de recursos externos para não criar ofuscamento com a latência no ambiente em teste.

## 14. Alternativas consideradas

**Uso continuado do wrapper interativo de benchmark (Ex: Measure-Command, PowerShell, /bin/time via cli script):** Abordagem defasada e de poluição massiva nos números; atrelar e computar o runtime Python instanciando bibliotecas em todos os testes oblitera as execuções de tempo puro do virtual emulador subjacente. A metodologia da E0 favorece a construção e injeção do medidor no mesmo plano lógico Python, dividindo minuciosamente todas as frações operadas pelo emulador in-process.

**Dependência Pytest-benchmark:** Facilita as corridas em paralelo, entretanto os ciclos contidos no framework geram dados enviesados quando mesclados na análise customizada O0 vs O1 exigida, somando amarra desnecessária na complexidade e extensibilidade com ELF, sem oferecer formato JSON que o projeto controle precisamente ou dependa (o módulo requer formatação fechada à vontade e layout restrito que difere do design ideal da E0). A decisão prevê um runner auditável mínimo contido no projeto `tools/benchmark.py`.

**Pyperf isolado:** Embora recomendável em análises da linguagem nativa Python (isolamento e estabilidade do SO), adiciona severo aumento da suíte de teste da infraestrutura; sua complexidade ao integrar os binários externos do ELF torna imperativo adotá-lo cautelosamente, sendo deixada em suspensão sem proibi-la de implantação tardia.

**Extensão e incremento nativo no executável com `--timings` publico:** Oferece dados transparentes imediatos sem runners externos; mas exige mutação direta na CLI da linguagem, afetando os tempos normativos e corrompendo a limpeza natural das saídas stdout para todos os usuários em uma funcionalidade precoce. Foi determinado encapsular a funcionalidade de métrica na área particular local de desenvolvimento.

**Critérios de Gates baseados temporalmente implementados agora:** Imprudência absoluta. Disparar uma recusa ou falha da pipeline em regressão temporal prematura sob computação não controlada por VMs partilhadas e com limitação de precisão não mensurada, antes da finalização técnica estrutural de base, impulsiona inconsistências. Exigirá histórico e maturidade base comprovada antes de uma nova aprovação ADR. 

**Antecipação da ação de otimização em detrimento à infraestrutura referencial estrita (otimização cega):** Resulta em micro-evolução focada isoladamente e insustentável a expansão massiva; uma infraestrutura de relatórios confiável balizada nos tempos de camadas exatas isoladas irá fundamentar toda futura adição técnica no runtime, prevenindo danos à saúde do software.

## 15. Consequências

**Positivas:**
- Decisões futuras no core algorítmico do S3 e backend são guiadas por números comprováveis, precisos, replicáveis e com isolamento adequado de fases.
- A diferenciação entre o tempo levado na serialização de leitura frente aos nanossegundos necessários do parser nativo será nítida e visível.
- Disputa comparativa direta com absoluta segurança entre as arquiteturas subjacentes (O0 para O1) atestando que todo e qualquer recurso ou folding implantado provê economia em ciclo real (tempo efetivo despendido) nos diversos workloads mapeados da categoria, sem que incorram em degradação sistêmica paralela na otimização de outros casos.
- Alicerce funcional capaz de mensurar as métricas intrínsecas e exatas operacionais do programa traduzido independentemente nativo ELF ao sistema Linux, com viés e tolerâncias desvinculados do runtime processual.
- Mitigação de implementação acidental e de acúmulo desproporcional de otimizações especulativas puramente acadêmicas, não ancoradas por retornos sensíveis absolutos no relatório.

**Negativas:**
- Agregação paralela na sustentabilidade arquitetônica da codebase.
- A dependência excessiva em nuvem dos dados obtidos nas plataformas CI irá sofrer interferências flutuantes por agendamentos e *noisy neighbors*, frustrando picos analíticos estritos ocasionais.
- Atrasos de rotinas nas pipelines locais e online pelo custo temporal de invocação repetitiva interativa e processamento contínuo inerentes.
- Bloqueio persistente (necessidade obrigatória na evolução paralela e manutenção isolada Linux) para medir a funcionalidade plena dos artefatos em compilação *native-asm/build/ELF* real do S3, criando barreira natural nas implementações diárias em estações puras Windows sem isolamento WLS compatível.
- Margem estreita de incerteza em que um microbenchmark projetado isoladamente e otimizado ao extremo na E1 ou superior desvie sua curva da vida natural refletida frente aos códigos finais maiores e completos na linguagem (Amdahl’s trap e sobre-ajuste da O1 a microarquitetura irreal).

## 16. Estado da decisão
Aprovada integralmente na oficialização documental do Marco 0.8 e fixada normativamente como padrão oficial para toda validação futura temporal e de otimização no S3.
