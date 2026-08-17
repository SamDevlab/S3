# Diagnósticos estruturados da toolchain hospedada

Status: normativo para a CLI hospedada a partir da primeira entrega do Marco
0.6.

## Interface

Todo comando da CLI aceita:

```text
--diagnostic-format text
--diagnostic-format json
```

Por ser uma opção global do parser, ela é aceita antes do comando ou depois
do caminho de origem. As duas formas selecionam o mesmo comportamento.

`text` é o padrão. Ele preserva mensagens, stdout, stderr e códigos de saída
anteriores. No modo texto, `--debug` repropaga a exceção Python para
desenvolvimento; sem essa opção, erros esperados e erros internos capturados
pela fronteira da CLI não imprimem traceback. A combinação
`--diagnostic-format json --debug` é uso inválido: a CLI emite um único
`S3E_CLI_USAGE` em JSON e termina com status 2, sem misturar traceback textual.

Erros do próprio parser usam status 2. Quando os argumentos contêm uma
solicitação válida de `--diagnostic-format json`, comando inexistente,
argumento ausente e opção desconhecida são estruturados. Um valor inválido ou
ausente para `--diagnostic-format` não estabelece o modo JSON; nesse caso o
argparse preserva sua apresentação textual.

O schema de diagnóstico é independente das versões da linguagem, da S3
Assembly e da IR JSON. Estas continuam em 0.5.0.

## Streams e códigos de saída

Resultados normais continuam em stdout. Diagnósticos são escritos em stderr.

- sucesso usa status 0;
- erro de programa, artefato, emulação, backend ou toolchain usa status 1;
- uso inválido da CLI usa status 2;
- `run-native` preserva o status do processo ELF executado.

No modo JSON, cada diagnóstico ocupa exatamente uma linha UTF-8 e contém um
único objeto JSON. Texto humano não é acrescentado ao mesmo stderr. Uma
execução bem-sucedida não emite objeto de diagnóstico.

## Envelope e versão

Campos obrigatórios:

```json
{
  "category": "syntax",
  "code": "S3E_PARSE_SYNTAX",
  "message": "expected ';' after return value; found '}'",
  "phase": "parsing",
  "schema": "s3-diagnostic",
  "schema_version": "1.0.0",
  "severity": "error"
}
```

`schema` é sempre `s3-diagnostic`. `schema_version` usa
`MAJOR.MINOR.PATCH`. Um consumidor deve rejeitar major desconhecido. Campos
compatíveis podem ser acrescentados em um minor novo; esclarecimentos que não
mudam a forma usam patch.

## Campos

Campos obrigatórios:

- `schema`: identidade do schema;
- `schema_version`: versão do schema;
- `severity`: atualmente `error`;
- `category`: classificação estável e ampla;
- `phase`: etapa hospedada que detectou a falha;
- `code`: identificador estável e independente da mensagem;
- `message`: explicação humana sem obrigação de formato para parsing.

Campos opcionais:

- `file`;
- `source`;
- `function`;
- `block`;
- `opcode`;
- `memory`;
- `index`;
- `value`;
- `lower_bound`;
- `upper_bound`;
- `limit`;
- `exit_code`;
- `notes`.

Campos sem dado conhecido são omitidos, nunca inventados e nunca emitidos como
`null`. Para bounds de memória, `lower_bound` é inclusivo e `upper_bound` é
exclusivo, acompanhando `[lower_bound, upper_bound)`. Outros intervalos
preservam na mensagem a convenção aplicável.

`notes` é uma lista de strings auxiliares. Consumidores não devem obter
categoria, código ou posição analisando `message` ou `notes`.

### Origem

`source` é um objeto com qualquer subconjunto conhecido de:

```text
offset, line, column, end_offset, end_line, end_column
```

Offsets são zero-based e não negativos. Linha e coluna são one-based e
positivas. Fins não podem preceder inícios. `end_line` e `end_column` aparecem
juntos. A implementação atual normalmente conhece apenas a posição inicial;
posições finais permanecem omitidas.

## Determinismo

A serialização:

- usa UTF-8;
- preserva caracteres não ASCII;
- ordena chaves lexicograficamente;
- não acrescenta espaços de apresentação;
- termina com um único newline;
- omite campos opcionais ausentes.

O mesmo diagnóstico produz os mesmos bytes.

## Categorias e códigos

Categorias hospedadas com uso atual:

```text
syntax
semantic
lowering
verification
artifact
version
overflow
bounds
uninitialized
immutable-write
frame-limit
instruction-limit
toolchain
unsupported-target
native-runtime
internal
```

Códigos públicos atuais:

```text
S3E_CLI_USAGE
S3E_IO
S3E_LEX_INVALID_CHARACTER
S3E_LEX_UNTERMINATED_STRING_LITERAL
S3E_LEX_TAB_INDENTATION
S3E_LEX_MIXED_INDENTATION
S3E_LEX_INVALID_DEDENT
S3E_PARSE_SYNTAX
S3E_PARSE_UNSUPPORTED_STRING_LITERAL
S3E_PARSE_OBSOLETE_BRACE
S3E_PARSE_OBSOLETE_SEMICOLON
S3E_PARSE_OBSOLETE_SWITCH
S3E_PARSE_EXPECTED_MATCH_ARM
S3E_PARSE_INVALID_MATCH_ARM
S3E_SEMANTIC_INVALID_PROGRAM
S3E_SEMANTIC_TYPE_MISMATCH
S3E_SEMANTIC_UNSUPPORTED_STRING_OPERATION
S3E_SEMANTIC_INVALID_RETURN_TYPE
S3E_SEMANTIC_INVALID_ARGUMENT_TYPE
S3E_SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE
S3E_SEMANTIC_REFERENCE_TARGET_UNINITIALIZED
S3E_SEMANTIC_REFERENCE_SHARED_WRITE
S3E_SEMANTIC_REFERENCE_ESCAPE
S3E_SEMANTIC_REFERENCE_RETURN
S3E_SEMANTIC_REFERENCE_NESTED
S3E_SEMANTIC_REFERENCE_AGGREGATE
S3E_SEMANTIC_REFERENCE_IDENTITY
S3E_SEMANTIC_REFERENCE_LOWERING_UNSUPPORTED
S3E_SEMANTIC_USE_AFTER_MOVE
S3E_SEMANTIC_BORROW_ESCAPE
S3E_SEMANTIC_BORROW_CONFLICT
S3E_SEMANTIC_BORROWED_OWNER
S3E_SEMANTIC_DYNAMIC_TYPE
S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED
S3E_MODULE_DUPLICATE
S3E_MODULE_NOT_FOUND
S3E_MODULE_CYCLE
S3E_MODULE_ENTRY_INVALID
S3E_IMPORT_DUPLICATE
S3E_IMPORT_CONFLICT
S3E_IMPORT_PRIVATE_SYMBOL
S3E_IMPORT_UNKNOWN_SYMBOL
S3E_TYPE_DUPLICATE
S3E_RECORD_FIELD_DUPLICATE
S3E_RECORD_FIELD_MISSING
S3E_RECORD_FIELD_UNKNOWN
S3E_ENUM_VARIANT_DUPLICATE
S3E_ENUM_VARIANT_UNKNOWN
S3E_MATCH_NON_EXHAUSTIVE
S3E_MATCH_DUPLICATE_ARM
S3E_LOWERING_INVALID_PROGRAM
S3E_VERIFY_INVALID_IR
S3E_INITIALIZATION_INVALID_ACCESS
S3E_INITIALIZATION_UNINITIALIZED
S3E_INITIALIZATION_IMMUTABLE_WRITE
S3E_ARTIFACT_INVALID_IR
S3E_ARTIFACT_INVALID_JSON
S3E_ARTIFACT_UNSUPPORTED_FORMAT
S3E_ARTIFACT_UNSUPPORTED_VERSION
S3E_ARTIFACT_INVALID_ASSEMBLY
S3E_CODEGEN_UNSUPPORTED_IR
S3E_ASSEMBLY_INVALID_PROGRAM
S3E_RUNTIME_OVERFLOW
S3E_RUNTIME_BOUNDS
S3E_RUNTIME_UNINITIALIZED_REGISTER
S3E_RUNTIME_UNINITIALIZED_MEMORY
S3E_RUNTIME_IMMUTABLE_WRITE
S3E_RUNTIME_FRAME_LIMIT
S3E_RUNTIME_INSTRUCTION_LIMIT
S3E_RUNTIME_INVALID_STATE
S3E_TERNARY_RANGE
S3E_NATIVE_BACKEND
S3E_TOOLCHAIN_NOT_FOUND
S3E_TOOLCHAIN_FAILED
S3E_UNSUPPORTED_TARGET
S3E_NATIVE_PROCESS_FAILED
S3E_INTERNAL
```

Uma mensagem pode ser melhorada sem mudar `code`. Uma mudança semântica de
categoria ou código exige revisão deliberada do contrato.

`S3E_SEMANTIC_TYPE_MISMATCH` pertence à categoria `semantic` e ocorre quando
análise semântica encontra tipos incompatíveis, incluindo combinações entre
`string`, `tryte` e `trit`. Exemplos incluem inicializar uma variável `string`
com valor `tryte`, passar `string` para parâmetro `tryte`, retornar `string` em
função declarada como `trit` ou atribuir uma expressão `trit` a uma variável
`string`.

## Exemplos

Erro sintático com origem:

```json
{"category":"syntax","code":"S3E_PARSE_SYNTAX","file":"fontes/programa.s3","message":"expected ';' after return value; found '}'","phase":"parsing","schema":"s3-diagnostic","schema_version":"1.0.0","severity":"error","source":{"column":1,"line":3,"offset":34}}
```

Bounds no emulador hospedado:

```json
{"block":"entry","category":"bounds","code":"S3E_RUNTIME_BOUNDS","function":"read","index":-1,"lower_bound":0,"memory":"m0","message":"[bounds] memory m0 index -1 is outside [0, 2)","opcode":"TLOAD","phase":"emulation","schema":"s3-diagnostic","schema_version":"1.0.0","severity":"error","upper_bound":2}
```

Target indisponível:

```json
{"category":"unsupported-target","code":"S3E_UNSUPPORTED_TARGET","message":"native build requires a Linux x86-64 host; detected Windows AMD64","phase":"toolchain","schema":"s3-diagnostic","schema_version":"1.0.0","severity":"error"}
```

## Fronteira do ELF nativo

O runtime ELF independente continua emitindo somente o protocolo textual
definido em `native-diagnostics.md`. Ele não implementa este schema JSON.

Em `run-native --diagnostic-format json`, a CLI hospedada não analisa o stderr
do ELF. Se o processo falhar, ela emite `S3E_NATIVE_PROCESS_FAILED`, conserva o
status em `exit_code` e inclui o stderr nativo bruto em `notes`. Esse wrapper
descreve a falha do processo; não afirma conhecer a categoria interna do
runtime.

Um protocolo estruturado emitido diretamente pelo ELF exigirá especificação,
versionamento, implementação no runtime assembly e testes nativos próprios em
trabalho futuro.
