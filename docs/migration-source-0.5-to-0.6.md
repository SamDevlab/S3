# Guia de Migração: Sintaxe Fonte 0.5 para 0.6 (Preview)

A sintaxe de fonte do S3 está em processo de evolução. A versão 0.6 traz uma gramática focada em indentação estruturada, com o objetivo de reduzir o ruído visual e melhorar a legibilidade.

**Aviso:** O modo `0.6` está atualmente em **preview**. A versão `0.5` continua sendo o padrão. Não recomendamos a migração de projetos muito grandes ou em produção neste momento.

## Ativando a Sintaxe 0.6

Para experimentar a nova sintaxe no pipeline de compilação ou execução, utilize a nova *flag* global `--source-syntax` da CLI:

```bash
# Executando um código com sintaxe 0.6
python -m bootstrap.s3 --source-syntax 0.6 run program.s3

# Emitindo IR a partir de um código 0.6
python -m bootstrap.s3 --source-syntax 0.6 ir program.s3
```

> A CLI do S3 exige explicitamente a ativação porque a migração interna ainda não foi concluída. A sintaxe 0.5 permanece o padrão quando a flag for omitida.

## O que muda sintaticamente?

O código S3 0.6 sofreu algumas alterações importantes na forma como blocos, tipos e declarações são escritos.

### 1. Fim das chaves `{}` e ponto-e-vírgula `;`

Blocos de código agora são puramente estruturados através da indentação. O ponto-e-vírgula também não é mais suportado no final de declarações e expressões (com exceção de strings ou contextos onde não é léxico). A introdução de um bloco é feita sempre por um `DOIS PONTOS (:)` e uma quebra de linha `NEWLINE`.

**Antes (0.5):**
```s3
fn main() -> tryte {
    return 1;
}
```

**Depois (0.6):**
```s3
fn main() -> tryte:
    return 1
```

### 2. Declaração de Variáveis e Tipagem

Na sintaxe 0.5, o tipo precedia o identificador. Agora, a declaração segue um padrão postfix (`identificador: tipo`), aproximando-se de linguagens mais modernas. Além disso, variáveis mutáveis requerem obrigatoriamente a palavra-chave `mut`.

**Antes (0.5):**
```s3
tryte value = 0;
```

**Depois (0.6):**
```s3
mut value: tryte = 0
```

Se o `mut` for omitido, a reatribuição não será permitida:

```s3
value: tryte = 0
value = 1 # Erro: atribuição a variável imutável (quando houver suporte futuro semântico, mas a sintaxe já exige o padrão)
```

### 3. Construções Unificadas

Recursos como controle de fluxo ternário (`match`) e suporte a coleções (`arrays` literais, leituras e atribuições indexadas) já foram reescritos e estão semanticamente integrados para ambos os modos. A diferença fica por conta exclusivamente da sintaxe baseada em indentação e pontuação simplificada.

Exemplo de match e arrays:

**0.6:**
```s3
fn main() -> tryte:
    values: tryte[3] = [1, 2, 3]
    match values[0]:
        1:
            return 1
        0:
            return 0
        -1:
            return 0
```

## Próximos Passos (Roadmap)

1. A migração completa das infraestruturas de parser da biblioteca padrão e emuladores internos está agendada para o Marco 0.6.
2. Após a conclusão, `0.6` será definida como o padrão.
3. Até lá, a gramática antiga (`0.5`) é mantida integralmente garantindo a continuidade do ecossistema.
