# Roadmap S3 0.53 — Typed Static Text Values

## Visão Geral
Habilita o tipo `string` na linguagem fonte S3 para representar valores de texto estáticos e imutáveis originados de literais de string (`"..."`).

## Sintaxe
```s3
# Atribuição e binding de texto estático
let msg: string = "hello world"

# Passagem de string como argumento de função
fn print_message(s: string) -> tryte:
    return 0

# Retorno de valor string
fn get_prefix() -> string:
    return "S3asm"
```

## Regras Semânticas e Validação
1. O tipo primitivo `string` é um tipo de valor imutável.
2. Bindings do tipo `string` armazenam referências a tabelas de literais estáticos (`StaticStringTable`).
3. Conversões implícitas entre `string` e `trit`/`tryte` são estritamente proibidas.
4. Parâmetros e retornos de funções podem utilizar o tipo `string`.
5. Operações de mutação, indexação ou modificação em `string` continuam rejeitadas nesta fase.

## Lowering e Execução
- Lowering mapeia literais e bindings de `string` para o identificador constante estático correspondente na `StaticStringTable` (ex: `s0`, `s1`).
- O emulador armazena os valores de string imutáveis no escopo do frame e permite passagem por argumento e retorno sem violação de limites.
