# Architecture Specification S3 0.53 — Typed Static Text Values

## Status
**Especificação Arquitetural Aprovada para o Milestone 0.53** (Fase de Especificação e Contrato. Nenhuma funcionalidade runtime ou alteração no compilador foi implementada nesta entrega).

---

## 1. Contexto e Suporte Pré-existente
O compilador S3 já possui suporte parcial a literais de string no front-end:
- **Lexer:** Reconhece literais entre aspas duplas como `TokenKind.STRING_LITERAL`.
- **AST:** Constrói nós `ast.StringLiteral`.
- **StaticStringTable:** Coleta e deduplica literais (`s0`, `s1`, ...) calculando hashes SHA-256 e metadata de bytes UTF-8 em `bootstrap/s3/static_strings.py`.
- **Validação Semântica:** Rejeita explicitamente a execução/lowering de literais com o código de diagnóstico `S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED`.

---

## 2. Objetivo da Especificação 0.53
Definir o contrato normativo para transformar literais de texto estáticos em valores tipados de primeira classe (`string`) na linguagem S3, **sem introduzir alocação em Heap, Garbage Collection ou dependência da libc**.

---

## 3. Definição do Modelo de Valor e Garantias

### 3.1. Modelo de Valor
`string` é um valor imutável e de primeira classe na linguagem fonte, mas representa **exclusivamente texto estático conhecido em tempo de compilação**. Não existe alocação dinâmica de memória em runtime.

### 3.2. Representação Conceitual
Um valor `string` é representado conceitualmente por um handle/índice estático que resolve para:
- Identificador estável da entrada na tabela estática (ex: `s0`, `s1`);
- Sequência de bytes UTF-8 imutáveis;
- Comprimento fixo em bytes (`byte_length`);
- Lifetime global durante toda a execução do programa.

O identificador do handle é abstrato e não depende de endereços de memória físicos do host ou da máquina.

### 3.3. Identidade e Igualdade
- A identidade interna utiliza o identificador da tabela estática (`s0`, `s1`).
- A semântica de igualdade (quando futuramente adicionada via `==`) será por conteúdo.
- Operadores de comparação (`==`, `!=`, `<`, `>`) não fazem parte da primeira entrega de runtime da 0.53.

### 3.4. Ausência de Ponteiros Públicos e Coerção
- O código S3 não observa endereços de memória físicos.
- O tipo `string` não é um inteiro disfarçado.
- Proibida qualquer conversão/coerção implícita ou explícita entre `string` e `trit` ou `tryte`.
- Proibida qualquer aritmética sobre strings.

### 3.5. Lifetime e Gerenciamento de Memória
- Todas as strings possuem lifetime global durante toda a execução.
- Não existe ownership, borrow checker, desalocação, Heap ou Garbage Collector.

---

## 4. Escopo Exato da Futura Implementação Runtime (Milestone 0.53 Runtime)

### 4.1. Incluído no Escopo Runtime Futuro
- Tipo fonte `string` em anotações de tipo.
- Literais de string como expressões válidas (`"hello"`).
- Bindings imutáveis (`let s: string = "..."`) e mutáveis (`let mut s: string = "..."`) contendo referências a handles estáticos.
- Passagem de `string` como parâmetro de função.
- Retorno de `string` em funções.
- Atribuição entre variáveis do tipo `string`.
- Suporte no Emulador hospedado.
- Suporte no Backend Nativo x86-64.
- Serialização determinística de IR e Assembly.

### 4.2. Não Incluído (Itens Explicitamente Adiados)
- Concatenação de strings (`+`).
- Interpolação de textos.
- Indexação por posição (`s[0]`) e slicing.
- Operadores de comparação (`==`, `!=`, `<`, etc.).
- Comprimento runtime `len(s)` (reservado para arrays estáticos de `tryte`/`trit`).
- Conversão entre `string` e arrays.
- Buffers mutáveis de texto.
- Construção de strings em runtime.
- FFI e integração com C.

---

## 5. Contrato de IR (Intermediate Representation)

1. **Tabela de Constantes Estáticas:**
   - O programa IR (`IRProgram`) mantém uma tabela de constantes de texto estáticas deduplicadas.
   - Cada entrada possui: `id` determinístico (`s0`, `s1`), `value` (string decodificada), `utf8_bytes`, `byte_count`, e `sha256`.
   - As entradas são ordenadas por primeira aparição no código fonte.

2. **Tipos e Instruções IR:**
   - O tipo `IRType.STRING` é adicionado aos tipos de registradores IR.
   - Uma nova instrução ou operando IR representa o carregamento da referência constante do handle estático: `IROpcode.CONST` estendido para strings ou instrução dedicada.
   - Registradores de tipo `IRType.STRING` transportam o identificador da constante sem alocação dinâmica.

3. **Serialização IR JSON:**
   - O envelope `s3-ir` 0.5.0 é preservado ou estendido de forma retrocompatível adicionando o campo `static_strings` no objeto raiz do programa.

---

## 6. Contrato de S3 Assembly (`.s3asm`)

1. **Seção de Dados Estáticos (`.data`):**
   - O formato S3 Assembly inclui uma seção `.data` no topo do arquivo para declarar constantes de texto:
   ```s3asm
   .s3asm 0.5.0
   .data
   s0 "hello world"
   s1 "S3_V0.6"
   ```
2. **Carregamento e Instrução Assembly:**
   - Registradores podem ser declarados com o tipo `string`.
   - Instrução `TCONST_STR r0:string, s0` para carregar a referência estática.
   - Passagem de argumentos e retornos utiliza os opcodes `TCALL` e `TRET` padronizados.

---

## 7. Contrato do Emulador Hospedado

1. **Tabela Global de Textos:**
   - O carregador do emulador registra a `StaticStringTable` do programa.
2. **Armazenamento de Registradores:**
   - Os registradores do frame configurados com tipo `string` armazenam a string literal / identificador estático `sN`.
3. **Passagem e Retorno:**
   - Argumentos de chamadas de função e valores de retorno são transferidos entre frames mantendo o identificador do handle.
4. **Verificação e Diagnósticos:**
   - O emulador valida a existência do handle estático. Referências a handles inexistentes disparam erro estruturado de emulação.

---

## 8. Contrato do Backend Nativo x86-64

1. **Seção de Dados Read-Only (`.rodata`):**
   - O backend nativo gera rótulos locais na seção `.rodata` do código assembly nativo ELF/AMD64:
   ```assembly
   .section .rodata
   .align 8
   .Ls0:
       .asciz "hello world"
   .Ls1:
       .asciz "S3_V0.6"
   ```
2. **Representação Física no Frame:**
   - No nível nativo x86-64, o registrador do frame armazena o endereço de 64 bits do rótulo estático (`lea rax, [rip + .Ls0]`).
3. **Passagem pela ABI System V AMD64:**
   - Os primeiros 6 argumentos do tipo `string` são passados via registradores de propósito geral (`rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`) como ponteiros de 64 bits para `.rodata`.
   - Retornos de função do tipo `string` usam `rax`.
   - Nenhum heap ou alocador runtime C/libc é utilizado.

---

## 9. Diagnósticos e Códigos de Erro (Schema `s3-diagnostic`)

Os seguintes códigos de erro devem ser aplicados ou adicionados:

1. `S3E_SEMANTIC_TYPE_MISMATCH`: Tentativa de atribuir `string` a `tryte`/`trit` ou vice-versa.
2. `S3E_SEMANTIC_UNSUPPORTED_STRING_OPERATION`: Tentativa de realizar adição (`+`), submissão a `len()`, indexação ou comparação sobre valores `string`.
3. `S3E_SEMANTIC_INVALID_RETURN_TYPE`: Retorno de `string` em função declarada para retornar `tryte`/`trit`.
4. `S3E_SEMANTIC_INVALID_ARGUMENT_TYPE`: Passagem de `string` para parâmetro do tipo `tryte`/`trit`.

---

## 10. Critérios de Aceitação para Futura Implementação Runtime

A futura entrega de código do Milestone 0.53 Runtime só será considerada aprovada se satisfizer todos os testes a seguir:

1. **Parser & AST:**
   - Parsing correto de `let x: string = "abc"`, `fn f(s: string) -> string`.
2. **Análise Semântica:**
   - Validação de tipos em assignments, chamadas e retornos.
   - Rejeição estrita de operações não suportadas (`+`, `[i]`, `len()`, `==`).
3. **Lowering & IR:**
   - Emissão determinística da tabela de strings no IR.
   - Deduplicação de literais de string idênticos.
4. **S3 Assembly & Round-trip:**
   - Geração e parsing correto de seções `.data` em `.s3asm`.
5. **Emulador:**
   - Execução determinística de programas com passagem e retorno de `string`.
6. **Backend Nativo x86-64:**
   - Compilação e execução ELF nativa em Linux x86-64 com paridade de resultados em relação ao emulador.
7. **Suíte de Regressão:**
   - Manutenção de 100% de aprovação nos testes existentes (`golden_inspect.py` e `compare_assembly_renderer.py`).
