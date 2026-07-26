# Architecture Specification S3 0.53 — Typed Static Text Values

## Status
**Proposta / Especificação de Arquitetura Arquivada** (Nenhuma funcionalidade de runtime ou alteração no compilador foi implementada nesta versão).

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

## 3. Não-Objetivos (Escopo Excluído)
- **Não há Heap ou Garbage Collector:** Toda string é estática (`.rodata`) e imutável.
- **Sem Concatenação Dinâmica em Runtime:** Operações de concatenação exigiram alocação dinâmica e ficam fora do escopo.
- **Sem Mutação:** Strings são estritas e imutáveis.
- **Sem Indexação por Posição ou Slicing Runtime:** Operações avançadas de manipulação de texto continuam diferidas.

---

## 4. Modelo de Tipo e Sintaxe Proposta

### 4.1. Declarando Valores de Texto Estáticos
```s3
# Binding de constante de texto
let msg: string = "hello world"

# Passagem de parâmetro em função
fn print_prefix(prefix: string) -> tryte:
    return 0

# Retorno de valor estático
fn get_tag() -> string:
    return "S3_V0.6"
```

### 4.2. Regras Semânticas
1. `string` é um tipo escalar imutável que representa uma referência a um identificador estático na `StaticStringTable` (ex: `s0`).
2. Proibida qualquer conversão implícita ou explícita entre `string` e `trit` ou `tryte`.
3. Atribuições repetidas são permitidas apenas se o binding for declarado como `mut` (`let mut s: string = "a"`).

---

## 5. Arquitetura de Lowering, IR e Backend Nativo (Proposta Técnica)

### 5.1. Representação no IR
- Propor um tipo `IRType.STRING` ou representação por ponteiro estático de handle `sN`.
- Manter uma tabela de constantes `.rodata` vinculada ao módulo/artefato IR.

### 5.2. Contrato no S3 Assembly (`.s3asm`)
- Extensão do cabeçalho do artefato para incluir seções de texto estático (`.data` / `.rodata`).
- Instrução `TCONST_STR r0, "hello"` ou vinculação por símbolo estático.

### 5.3. Contrato no Emulador Hospedado
- O emulador gerencia uma tabela global de constantes lógicas imutáveis, armazenando handles no registrador do frame sem alocação dinâmica.

### 5.4. Contrato no Backend Nativo x86-64
- Emissão de seção `.rodata` com rótulos `s0: .asciz "hello"`.
- O registrador do frame armazena o endereço estático de memória (RIP-relative offset).

---

## 6. Decisões Arquiteturais Pendentes e Critérios de Aceitação para Implementação

Antes de iniciar a implementação do código no compilador em versões futuras, os seguintes pontos devem estar resolvidos:
1. **Especificação de Formato IR:** Formalização do esquema JSON e representação textual de IR para constantes não escalares.
2. **Especificação de Assembly `.s3asm`:** Decisão sobre representação de seções de dados estáticos em S3 Assembly.
3. **ABI Native Pass-by-Reference:** Garantia de compatibilidade com a System V AMD64 ABI sem estourar frames.

---

## 7. Matriz de Riscos
- **Risco:** Incompatibilidade do formato de artefato IR JSON 0.5.0 caso novos campos de dados estáticos sejam introduzidos de forma destrutiva.
- **Mitigação:** Manter a versão da IR estável ou propor um incremento não-quebrante versionado.
