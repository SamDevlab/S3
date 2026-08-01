# Especificação da linguagem S3

Status: normativa para o compilador atual. Reflete a sintaxe 0.6 (indentation-based).
A sintaxe 0.5 (com `{`, `}`, `;` e `switch`) é considerada legada/deprecated e mantida apenas para compatibilidade.

## Funções e tipos escalares

Uma unidade contém funções com nomes únicos e exatamente uma `main` sem parâmetros.
Assinaturas são coletadas antes dos corpos, permitindo forward calls e recursão.
Parâmetros e retornos possuem tipos explícitos, que devem ser `trit` ou `tryte`.

`trit` representa `-1`, `0`, `1`; `tryte` representa `[-364, 364]`. Não há conversão implícita nem tipos unsigned. Overflow continua sendo erro. Não existem ponteiros nem alocação no heap.

```s3
fn main() -> tryte:
    return 0
```

## Léxico e blocos por indentação

A linguagem S3 (sintaxe 0.6) é baseada em indentação, abandonando `{}` e `;`.

Palavras-chave: `module`, `from`, `import`, `as`, `export`, `record`, `enum`,
`fn`, `return`, `match`, `while`, `mut`, `trit`, `tryte`, `case` (removido no
parser atual, usa-se literais diretos no match).

Identificadores seguem `[A-Za-z_][A-Za-z0-9_]*`.
Comentários começam com `#` (não mais `//`).

Blocos de código iniciam-se após um `:` seguido de quebra de linha e indentação.

Programas de arquivo unico continuam validos sem declaracao de modulo. A
compilacao multi-file usa declaracoes opcionais `module`, imports explicitos
`from ... import ...` e funcoes exportadas com `export fn`, conforme
[modules.md](modules.md). Nao ha package manager, wildcard import ou resolucao
baseada em ordem acidental do filesystem.

## Bindings e mutabilidade

Declarações possuem tipos explícitos e são imutáveis por padrão:

```s3
value: tryte = 10
```

A palavra-chave `mut` permite atribuição posterior:

```s3
mut value: tryte = 10
value = value + 1
```

A atribuição é um statement e não produz valor. O alvo deve existir, ser mutável e ter o mesmo tipo do valor. Toda declaração exige inicializador.

## Arrays estáticos

Arrays têm tamanho fixo avaliado em tempo de compilação:

```s3
mut values: tryte[4] = [1, 2, 3, 4]
values[1] = 5
return values[0]
```

- Elementos devem ser `trit` ou `tryte`.
- Uma única dimensão. Arrays aninhados são erro.
- Literal obrigatório com exatamente o comprimento declarado.
- Apenas arrays mutáveis aceitam atribuição indexada.
- Não há atribuição/cópia de array inteiro.
- Arrays não podem ser passados como argumentos nem retornados de funções.
- O índice tem tipo `tryte`. Índice fora da faixa é erro (semântico se constante, em execução se calculado).
- A operação `len(array)` retorna a quantidade de elementos do array como um `tryte` avaliado estaticamente em tempo de compilação.

```s3
values: tryte[5] = [10, 20, 30, 40, 50]
mut total: tryte = 0
for i: tryte in range(0, len(values)):
    total = total + values[i]
```

## Strings estáticas

Strings estáticas são suportadas apenas como literais definidos na compilação. O tempo de execução não fornece manipulação nativa de strings arbitrárias. Literais de string estão presentes na sintaxe para suporte a chamadas nativas de diagnóstico (renderização).

Uma `string` e um valor de texto estatico de capacidade fixa. A capacidade e o
byte length UTF-8 do texto decodificado conhecido em tempo de compilacao; o
terminador NUL usado pelo backend nativo em `.rodata` nao faz parte do valor da
linguagem. O valor em runtime e um handle escalar imutavel para armazenamento
estatico. S3 nao expoe ponteiros, aritmetica de handles, heap, desalocacao,
garbage collection ou buffers mutaveis de texto.

Operacoes de texto como `len(text)`, index, slice, igualdade, `contains`,
`starts_with`, `ends_with`, `find`, `upper`, `lower`, `trim`, `repeat` e
`replace` sao avaliadas somente quando seus operandos sao expressoes de texto
estatico conhecidas pela analise semantica. Operacoes equivalentes sobre texto
dependente de parametros, bindings mutaveis ou chamadas nao constantes
continuam rejeitadas.

## Records e enums

Records e enums fechados sao tipos nominais especificados em
[composite-types.md](composite-types.md). Records possuem campos nomeados em
ordem declarada e sao scalarizados internamente. Enums usam discriminants
`tryte` deterministicos e podem declarar payloads de layout fixo conforme
ADR-0021. O layout de enum payload e tag primeiro, payload depois, largura fixa
por tipo, e slots inativos inicializados deterministicamente.

Modulos podem exportar tipos nominais com `export record` e `export enum`.
Imports explicitos podem trazer tipos exportados para o namespace de tipos do
modulo consumidor, e tipos pontuados como `geometry.Point` preservam a
identidade nominal do modulo definidor. Essa identidade e `ModuleId + TypeName`;
tipos same-name ou same-shape de modulos diferentes continuam incompatíveis.

Records multi-campo nao podem ser retornados ate que exista uma ABI agregada
propria. Enums sem payload continuam retornaveis como discriminants escalares.
Enums com largura total maior que uma celula podem ser usados em locals,
parametros, copias, branches, loops e match, mas nao podem ser retornados pela
ABI atual. `match` sobre enum exige cobertura exaustiva ou `else`; arms
explicitos de variants com payload podem introduzir bindings locais tipados.

## Expressões e operadores

Da maior para a menor precedência:

1. Chamada, indexação, acesso a membro `.`, parênteses
2. Inversão unária `~` e negação `-`
3. Adição `+` e subtração `-`
4. Mínimo tritwise `&`
5. Máximo tritwise `|`
6. Comparação ternária `<=>`
7. Operadores relacionais `==`, `!=`, `<`, `<=`, `>`, `>=`

Expressoes postfix encadeiam da esquerda para a direita a partir de uma expressao
primaria. O parser trata `.` como acesso uniforme a membro; a analise semantica
decide se o membro representa simbolo de modulo, variante de enum ou campo de
record. O contrato normativo esta em [postfix-expressions.md](postfix-expressions.md).

Operadores relacionais comparam dois operandos do mesmo tipo escalar (`tryte` com `tryte`, ou `trit` com `trit`) e retornam `trit` (`-1` para verdadeiro, `0` para falso). `<=>` retorna `trit`. Subtração é reduzida exclusivamente a `INVERT` seguido de `ADD`; não existe opcode de subtração nativo.

## Controle de fluxo: match, while e for

Os comandos de controle de fluxo de laço `break` e `continue` são suportados dentro de laços `while` e `for`. `break` encerra imediatamente o laço e transfere o controle para o bloco após o laço mais interno. `continue` encerra a iteração corrente e transfere o controle para a reavaliação da condição do `while` ou para o passo de incremento do `for`. Não possuem rótulos (labels) ou argumentos de expressão.

O `match` substitui o antigo `switch` e exige um seletor do tipo `trit`. Exige o mapeamento explícito e obrigatório dos três casos `-1`, `0` e `1`. Além do statement `match`, o `match` também é aceito no nível de expressão (`MatchExpression`). Em modo expressão, cada braço contém uma única expressão de resultado e apenas o braço selecionado é avaliado em tempo de execução.

```s3
fn sign(value: tryte) -> trit:
    match value <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
```

O `while` avalia uma condição do tipo `trit`:
- Se for `-1`, o corpo é executado.
- Se for `0`, o laço termina.
- Se for `1`, o laço termina.

O laço `for` itera deterministicamente sobre intervalos `range(start, end)` de `tryte` no intervalo meio-aberto `[start, end)`:

```s3
fn main() -> tryte:
    mut total: tryte = 0
    for i: tryte in range(0, 5):
        total = total + i
    return total
```

## Retorno

Funções não retornam implicitamente. Todas as rotas de código devem convergir para um `return` compatível. Um `while` não garante execução de seu corpo (mesmo com `-1` constante na sintaxe atual, por segurança conservadora), então o código subsequente deve tratar a continuação do fluxo. Instruções `break` e `continue` terminam o bloco local mas não satisfazem o retorno da função. Código inalcançável (após `return`, `break`, `continue` ou `match` terminante) é rejeitado na compilação.

O contrato de retorno publico permanece escalar. `RETURN`, `TRET` e o caminho
nativo x86-64 retornam um unico valor. Records, incluindo nested records,
podem ser retornados somente quando o layout canonico contem exatamente uma
folha escalar. Enums podem ser retornados somente quando o layout total do tipo
contem exatamente uma celula. Records ou enums com multiplas celulas sao
rejeitados antes do backend ate que uma ABI explicita de retorno agregado
exista.
