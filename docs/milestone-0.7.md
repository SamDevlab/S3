# Marco 0.7

## Estado

E0 normativa concluída. E1 paridade hospedada concluída. E2 instrumentação nativa implementada. E3 (validação ELF real) concluída e integrada na branch `main`.
O estado funcional do Marco 0.7 está concluído. A E4 (fechamento documental, empacotamento e versão 0.7.0) está encerrada; a tag v0.7.0 e a GitHub Release foram publicadas.

Todos os critérios de aceitação foram satisfeitos. A CI da `main` (Run 28745917775) validou:
- 622 passed por job Python (3.11, 3.12, 3.13);
- 92 passed no job nativo x86-64, sem skips.

As versões foram preservadas (fonte 0.6, IR 0.5.0, Assembly 0.5.0, schema 1.0.0), a compatibilidade V0.5 continua explícita sem fallback, e nenhum item fora do escopo foi incorporado. Os riscos residuais relativos à exaustão diferente em O0/O1 e ao contador global foram assumidos.

Este documento fecha o escopo do Marco 0.7 conforme o
[ADR-0014](decisions/ADR-0014-hosted-and-native-instruction-limit.md). A E0
formalizou a decisão normativa, a E1 implementou a paridade hospedada e a E2
implementou a instrumentação nativa; a E3 concluiu a validação ELF; a E4 é o fechamento final, concluído com a publicação da versão 0.7.0.

## Decisão normativa

O baseline do marco é a distribuição `s3-bootstrap` 0.6.0 no commit
`5b2a92128470af1084a18c7cb8d6d62b6addbca9`, marcado por `v0.6.0`.

O escopo aprovado é exclusivamente a paridade do limite de instruções entre o
emulador hospedado e o runtime Linux x86-64. Nenhuma outra direção Pós-MVP
integra o Marco 0.7.

Cache de artefatos, métricas ou novos passes de otimização, otimizações entre
blocos e ARM64 continuam futuros. Também permanecem fora do marco todas as
mudanças de linguagem, formatos e targets enumeradas em
[Fora de escopo](#fora-de-escopo).

## Motivação

O emulador interrompe execuções que atingem `100000` instruções por padrão e
aceita outro limite por API. O ELF Linux x86-64 limita frames, mas não
instruções. Assim, um ciclo estrutural é uma falha controlada no emulador e
pode executar indefinidamente no binário nativo.

Essa assimetria enfraquece a previsibilidade operacional e impede afirmar
paridade de limites entre os dois mecanismos de execução.

## Objetivo

Implementar um orçamento global e determinístico de
instruções S3 no emulador e no runtime Linux x86-64, com configuração pública,
falha controlada e diagnóstico equivalente, sem mudar a linguagem ou os
formatos persistentes.

Ao final do marco, um programa que tenta executar a instrução posterior ao
orçamento deve falhar antes dessa instrução, com status 1 e contexto do ponto
lógico. Programas que terminam dentro do orçamento devem preservar seus
resultados atuais.

## Escopo incluído

- preservar a unidade e a ordem de contagem formalizadas na E0;
- expor um limite positivo na CLI e nas APIs de execução e geração nativa;
- preservar `100000` como limite padrão;
- aplicar um contador global por execução, incluindo chamadas recursivas;
- instrumentar o backend Linux x86-64 para falhar antes da instrução excedente;
- emitir diagnóstico hospedado e nativo de categoria `instruction-limit`;
- manter emissão nativa determinística para a mesma entrada e configuração;
- cobrir emulador, assembly nativa, ELF, O0/O1 e compatibilidade de artefatos;
- manter ADR, arquitetura, especificações de otimização e diagnósticos nativos
  coerentes com a decisão aprovada.

## Fora de escopo

- cache de artefatos;
- métricas ou novos passes de otimização;
- alteração de O0/O1 além da instrumentação do limite;
- novos opcodes, diretivas, tipos ou construções da linguagem;
- mudança da sintaxe fonte, gramática, AST ou semântica;
- mudança dos formatos IR JSON ou S3 Assembly;
- protocolo JSON emitido diretamente pelo ELF;
- alteração do schema `s3-diagnostic`;
- limite de tempo, memória física ou syscalls;
- ARM64, Windows, macOS ou outro backend;
- ponteiros, heap, globals, strings, módulos, I/O ou autohospedagem;
- correção do F841 histórico em `initialization.py`.

## Comportamento atual

No baseline 0.6.0:

- `Emulator` e `execute_assembly` aceitam `max_instructions`, cujo padrão é
  `100000`;
- o emulador testa o orçamento antes de selecionar a próxima instrução,
  incrementa o contador uma vez e então executa o opcode;
- o contador hospedado é global para a execução e inclui instruções em frames
  chamados;
- excesso produz `S3E_RUNTIME_INSTRUCTION_LIMIT`, categoria
  `instruction-limit`, fase `emulation`, função, bloco e limite;
- `DEFAULT_MAX_INSTRUCTIONS = 100_000` centralizado em `emulator.py`, eliminando
  os dois literais isolados;
- `Emulator`, `execute_assembly` e `run_source` aceitam e propagam `max_instructions`;
- `s3 run --max-instructions N` aceita inteiro positivo e propaga até o `Emulator`;
- zero e valores negativos são rejeitados com mensagem de uso (CLI) ou `ValueError` (API);
- `--max-instructions` está ausente de `native-asm`, `build` e `run-native` nesta E1;
- diagnóstico `S3E_RUNTIME_INSTRUCTION_LIMIT` preservado sem alteração;
- orçamento global confirmado por testes: chamadas, recursão, TCALL, TRET e TJMP;
- nenhuma versão alterada.
- `X8664Backend`, `generate_native_assembly` e `X8664Emitter` recebem somente o
  limite de frames;
- o runtime nativo possui contador privado de frames, mas nenhum contador de
  instruções nem categoria nativa correspondente;
- ciclos nativos dependem de interrupção externa;
- O1 é local e a quantidade de instruções emitidas pode ser menor que em O0.

## Comportamento aprovado

Uma instrução S3 Assembly executada consome exatamente uma unidade. Isso inclui
`TCALL`, `TRET`, saltos, branches, loads e stores. Prólogos, epílogos, checks,
helpers, syscalls e instruções físicas x86-64 não consomem unidades adicionais.

O contador começa em zero antes de `main` e é compartilhado por todos os frames
S3 do processo. Antes de executar cada opcode:

1. se o contador for igual ao limite, a execução falha no site do opcode
   pendente;
2. caso contrário, o contador é incrementado uma vez;
3. o opcode é executado.

Logo, um limite `N` permite no máximo `N` instruções S3 concluídas. O limite
deve ser inteiro positivo; zero e valores negativos são erro de uso ou de API.
Para o runtime Linux x86-64, devido à arquitetura do contador físico, é imposto
o domínio de 64 bits sem sinal (`u64`), definindo a faixa nativa rigorosa:
`1 <= max_instructions <= 18446744073709551615` (`2**64 - 1`).

O orçamento incide sobre o S3 Assembly efetivamente selecionado depois de O0
ou O1. Portanto, limites artificialmente baixos podem alcançar pontos
diferentes nos dois níveis. Essa falha de recurso não deve autorizar diferenças
em resultados ou falhas semânticas quando ambas as execuções terminam dentro
do orçamento.

## Sintaxe

Não muda. V0.6 permanece o default e V0.5 permanece disponível somente por
seleção explícita.

## Gramática

Não muda. Nenhum token, produção ou regra de indentação é acrescentado.

## AST

Não muda. O limite é configuração da execução, não um nó da linguagem.

## Análise semântica

Não muda. A análise não aceita nem rejeita programas com base no orçamento de
execução. Ciclos estruturais continuam válidos.

## Diagnósticos

O emulador deve preservar:

- categoria `instruction-limit`;
- código `S3E_RUNTIME_INSTRUCTION_LIMIT`;
- fase `emulation`;
- status 1 na CLI hospedada.

Quando conhecidos, o diagnóstico deve incluir função, bloco, opcode, origem e
`limit`. O texto público atual do emulador deve ser preservado salvo decisão
normativa explícita.

O runtime ELF deve acrescentar a categoria textual `instruction limit` ao
contrato de `native-diagnostics.md`, com função, bloco, opcode, origem e limite.
Ele continua escrevendo em stderr e encerrando com status 1. Em
`run-native --diagnostic-format json`, a CLI continua emitindo somente
`S3E_NATIVE_PROCESS_FAILED` e preservando o stderr nativo em `notes`; ela não
deve interpretar o texto do ELF.

O schema `s3-diagnostic` permanece em 1.0.0 porque a categoria, o código e o
campo `limit` hospedados já existem.

## IR

Não muda. O orçamento não é serializado na IR, não altera invariantes e não
introduz opcode ou metadado. O formato permanece `s3-ir` 0.5.0.

## Assembly

Não muda. O orçamento é configuração do executor/backend e não uma diretiva do
programa. A instrução contada é cada opcode já existente. O formato permanece
S3 Assembly 0.5.0, inclusive a leitura explícita de legado já suportado.

## Runtime ou VM

O emulador deve centralizar o default em uma constante pública e propagá-lo por
`run_source` e pela CLI sem alterar a ordem atual de check, incremento e
execução.

O runtime ELF deve possuir um contador privado, inicializado por processo e
inacessível ao programa S3. A instrumentação deve ocorrer uma vez no início da
emissão de cada opcode, antes de efeitos, acessos, chamadas ou retornos.
Helpers internos não podem incrementar o contador.

## Backend nativo

`X8664Backend`, `generate_native_assembly` e `X8664Emitter` devem receber um
limite positivo. O valor deve ser incorporado deterministicamente à assembly
gerada.

Cada site instrumentado deve apontar para um handler de falha controlada, sem
acesso perigoso posterior. O contador é estado privado do runtime e não cria
memória global observável na linguagem.

O suporte continua exclusivamente Linux x86-64. Uma implementação só pode ser
considerada concluída depois de execução ELF real no job nativo obrigatório;
inspeção textual em Windows não substitui essa validação.

## CLI e API pública

A implementação futura acrescentará:

```text
--max-instructions N
```

O default é `100000`. A opção afeta `run`, `native-asm`, `build` e
`run-native`; comandos que apenas inspecionam ou verificam artefatos não
executam orçamento e devem rejeitar a opção, nunca ignorá-la silenciosamente.

`run_source` deve aceitar `max_instructions`. `X8664Backend` e
`generate_native_assembly` devem aceitar o mesmo conceito. Parâmetros
existentes e seus defaults permanecem compatíveis.

Valores menores que 1 devem falhar explicitamente. A CLI deve usar seu contrato
de uso e diagnóstico estruturado; APIs Python devem rejeitar o valor antes da
emissão ou execução.

## Compatibilidade

Fontes V0.5 e V0.6 preservam seleção e semântica atuais. Não haverá
autodetecção, fallback, segunda tentativa de parser ou migração implícita.

IR JSON e S3 Assembly 0.5.0 continuam aceitos exatamente como hoje. Como o
limite não integra esses formatos, não há conversão de artefato.

O comportamento de programas que terminam dentro do orçamento é compatível.
Programas nativos que ultrapassam o novo default passam de execução não
limitada para falha controlada. Essa mudança observável está formalmente
aprovada para o Marco 0.7.

## Migração

Nenhuma migração de fonte ou artefato é necessária. Usuários que executam
programas intencionalmente longos devem selecionar explicitamente um limite
maior. Não se propõe um modo ilimitado implícito.

## Segurança e limites

- o limite é validado antes de ser incorporado ou usado;
- o contador não pode sofrer wraparound antes da comparação;
- a falha ocorre antes dos efeitos da instrução excedente;
- recursão e chamadas compartilham o mesmo orçamento;
- o limite de frames continua independente;
- o limite de memória lógica continua independente;
- emissão e diagnósticos permanecem determinísticos;
- o contador não é endereçável pela linguagem;
- o mecanismo não promete proteção contra custo elevado dentro de helpers
  físicos, assembler, linker ou syscalls.

## Testes obrigatórios

- unidade: validação de limites `1`, zero e negativo nas APIs;
- emulador: exatamente `N` instruções passam e a instrução `N + 1` falha;
- emulador: ciclo, chamada e recursão compartilham o contador;
- diagnósticos hospedados: categoria, código, fase, limite, função, bloco,
  opcode e origem quando disponíveis;
- CLI: default, opção explícita, valor inválido, texto, JSON e códigos de saída;
- backend: instrumentação única por opcode e ausência em helpers;
- backend: assembly idêntica para a mesma entrada/configuração e diferente
  somente quando a configuração muda;
- ELF Linux x86-64: limite exato, ciclo, chamadas, recursão e status 1;
- diagnóstico nativo: categoria, contexto, limite e stderr;
- diferencial: resultados iguais entre emulador/nativo e O0/O1 quando todos
  terminam dentro do orçamento;
- limites baixos: comportamento documentado de O0/O1 conforme o Assembly
  efetivamente executado;
- regressão: todos os exemplos oficiais, overflow, bounds, inicialização,
  imutabilidade e frame limit;
- compatibilidade: fonte V0.5 explícita, fonte V0.6 default, IR 0.5.0, Assembly
  0.5.0 e rejeição das versões futuras atuais;
- serialização: nenhum campo novo em IR ou Assembly;
- nativo obrigatório: nenhuma transformação de falha em skip.

## Critérios de aceitação

1. O ADR-0014 permanece como autoridade para unidade, ordem de contagem,
   default e interação com O0/O1.
2. A documentação normativa não contém contradições sobre limites nativos.
3. O emulador e a API pública expõem o mesmo default sem regressão.
4. O ELF falha antes da instrução excedente, com status 1 e contexto normativo.
5. A CLI configura execução hospedada e nativa de forma documentada.
6. Fonte, gramática, AST, IR, Assembly e schema de diagnóstico mantêm suas
   versões atuais, salvo nova justificativa independente.
7. V0.5 continua explícita e não existe fallback ou autodetecção.
8. A suíte local, compileall e Ruff não apresentam regressões novas.
9. A matriz Python 3.11–3.13 e o job Linux x86-64 obrigatório ficam verdes.
10. O job nativo executa os testes do limite sem skips.
11. Nenhum item das outras direções Pós-MVP entra no diff.

## Estratégia de entregas

1. **E0 — decisão normativa (concluída):** registrar ADR e ajustar as
   especificações de otimização, runtime e diagnósticos antes do código.
2. **E1 — paridade hospedada (concluída):** constante
   `DEFAULT_MAX_INSTRUCTIONS` centralizada, `max_instructions` exposto em
   `run_source` e `execute_assembly`, opção `--max-instructions` adicionada ao
   comando `run`, validação de valores inválidos, testes de contador global,
   diagnóstico preservado.
3. **E2 — instrumentação nativa (concluída):** implementar contador, handlers e testes
   unitários da assembly sem alterar a toolchain. Adicionada a flag para os
   comandos `native-asm`, `build` e `run-native`.
4. **E3 — validação ELF (concluída e integrada):** executar diferenciais e limites reais no Linux
   x86-64 obrigatório, incluindo O0/O1 e reprodutibilidade.
5. **E4 — fechamento (concluída; versão 0.7.0 publicada):** auditar compatibilidade, documentação, empacotamento e
   preparar a distribuição 0.7.0 sem mudar as versões dos formatos.

Cada entrega deve ser pequena, revisável e manter a suíte verde. O Marco 0.7 encerra-se com a E4.

## Riscos

- instrumentação aumenta tamanho e custo de todos os opcodes nativos;
- um contador global acessado por opcode pode reduzir desempenho;
- limites baixos podem divergir entre O0 e O1 porque o Assembly executado muda;
- escolher `100000` como default nativo torna finitos alguns programas antes
  não limitados;
- contexto do site excedente precisa permanecer correto após otimização;
- falha na ordem check/incremento pode criar erro de fronteira;
- reutilizar o contador de frames confundiria limites independentes;
- omitir opcodes ou contar helpers quebraria a equivalência proposta;
- mudanças na assembly gerada exigem revalidar reprodutibilidade e diagnósticos
  nativos.

## Decisões encerradas pela E0

1. O limite hospedado e nativo é o único escopo do Marco 0.7.
2. O default compartilhado é `100000`, sem modo ilimitado implícito.
3. O orçamento conta o S3 Assembly posterior a O0 ou O1; exaustão em pontos
   diferentes sob limites baixos é aceitável.
4. `--max-instructions` será restrito a `run`, `native-asm`, `build` e
   `run-native`.
5. A distribuição destinada ao fechamento é 0.7.0; fonte 0.6, IR 0.5.0,
   Assembly 0.5.0 e schema diagnóstico 1.0.0 permanecem inalterados.

A E0 termina com este contrato documental. A implementação começa somente na
E1, em uma entrega separada.
