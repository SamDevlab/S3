# ADR-0012: diagnósticos estruturados da toolchain hospedada

- Status: aceito
- Data: 2026-07-04

## Contexto

As camadas 0.5 preservam boa origem e contexto, mas suas exceções terminam em
mensagens textuais. Ferramentas precisariam analisar frases instáveis para
descobrir categoria, fase, posição, função, bloco, opcode ou valores. Ao mesmo
tempo, o texto atual é interface humana compatível e o runtime ELF não possui
um serializador JSON.

## Decisão

Adotar um modelo `Diagnostic` tipado na toolchain Python, independente de
`argparse` e do backend x86-64. Categorias, fases e códigos são enums
centralizados. Exceções públicas mantêm seu texto e carregam ou fornecem
metadados ao adaptador central, sem parsing de mensagens.

A CLI oferece uma opção global e uniforme:

```text
--diagnostic-format text|json
```

`text` permanece padrão. `json` emite em stderr um objeto por linha, no schema
`s3-diagnostic` 1.0.0, UTF-8, chaves ordenadas e campos ausentes omitidos. A
CLI é o único ponto de apresentação. Erros internos usam código estável e não
mostram traceback por padrão. Em texto, `--debug` os repropaga. A combinação
de JSON com `--debug` é rejeitada como `S3E_CLI_USAGE`, com status 2 e sem
traceback textual, preservando a propriedade de um único objeto no stderr.

Erros do argparse são estruturados quando uma solicitação válida de JSON pode
ser identificada nos argumentos. Um valor inválido ou ausente para a própria
opção de formato permanece textual, pois não seleciona JSON.

O schema possui versionamento próprio. Linguagem, S3 Assembly e IR JSON
continuam em 0.5.0.

## Runtime ELF

O ELF preserva seu diagnóstico textual 0.5. A CLI não interpreta esse texto
para fabricar categoria ou contexto JSON. Em modo JSON, `run-native` relata
somente que o processo falhou, preservando status e stderr bruto como nota.
Isso não é suporte JSON direto do runtime.

## Alternativas rejeitadas

- analisar mensagens com expressões regulares: frágil e tornaria texto uma API
  semântica acidental;
- serializar JSON em cada lexer, parser, verifier e emulador: espalharia
  política de apresentação pelas fases;
- substituir imediatamente todas as exceções por uma grande hierarquia:
  ampliaria a refatoração e quebraria consumidores Python;
- emitir todos os opcionais como `null`: aumenta ruído e confunde ausência com
  valor conhecido;
- mudar o padrão para JSON: quebraria uso humano e scripts existentes;
- implementar JSON no runtime assembly nesta entrega: exigiria protocolo,
  strings, escape e testes nativos desproporcionais ao escopo.

## Consequências

Ferramentas podem depender de schema, categoria, código e campos explícitos,
enquanto mensagens humanas podem evoluir. O custo é manter a taxonomia e
versionar mudanças incompatíveis.

Exceções existentes continuam públicas e seus `str()` permanecem compatíveis.
stdout e códigos de saída são preservados. A fronteira hospedada cobre
frontend, IR, artefatos, emulador, backend e toolchain; o protocolo direto do
ELF fica explicitamente pendente.

## Limites desta entrega

Não inclui cache, métricas de otimização, limite nativo de instruções,
otimizações entre blocos, ARM64, novos opcodes, arrays em assinaturas, heap,
ponteiros, strings, módulos, I/O da linguagem ou autohospedagem.
