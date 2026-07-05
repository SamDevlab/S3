# Guia de Migração: Sintaxe Fonte 0.5 para 0.6

A sintaxe de fonte do S3 está em processo de evolução. A versão 0.6 traz uma gramática focada em indentação estruturada, com o objetivo de reduzir o ruído visual e melhorar a legibilidade.

V0.6 é o padrão do frontend e dos comandos da CLI. Os exemplos oficiais já
usam essa sintaxe. V0.5 permanece temporariamente suportada, mas exige seleção
explícita. Não existe autodetecção, fallback ou migração automática.

## Selecionando a versão da fonte

Programas V0.6 usam os comandos comuns sem opção adicional:

```bash
python -m bootstrap.s3.cli run program.s3
python -m bootstrap.s3.cli ir program.s3
```

Para executar uma fonte V0.5, selecione-a explicitamente:

```bash
python -m bootstrap.s3.cli --source-syntax 0.5 run legacy.s3
```

O compilador não tenta uma segunda gramática quando a análise falha.

## O que muda sintaticamente?

O código S3 0.6 sofreu algumas alterações importantes na forma como blocos, tipos e declarações são escritos.

### 1. Fim das chaves `{}` e ponto-e-vírgula `;`

Blocos de código agora são puramente estruturados através da indentação. O ponto-e-vírgula também não é mais suportado no final de declarações e expressões. A introdução de um bloco é feita sempre por um `DOIS PONTOS (:)` e uma quebra de linha `NEWLINE`. Strings continuam fora do escopo da linguagem atual.

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

Declaração imutável:

**Antes (0.5):**
```s3
tryte value = 0;
```

**Depois (0.6):**
```s3
value: tryte = 0
```

Declaração mutável:

**Antes (0.5):**
```s3
mut tryte value = 0;
```

**Depois (0.6):**
```s3
mut value: tryte = 0
```

Se o `mut` for omitido, a reatribuição não será permitida:

```s3
value: tryte = 0
value = 1 # Erro semântico: atribuição a variável imutável
```

### 3. Construções Unificadas

Recursos como controle de fluxo ternário (`match`) e suporte a coleções (`arrays` literais, leituras e atribuições indexadas) já foram reescritos e estão semanticamente integrados para ambos os modos. A diferença fica por conta exclusivamente da sintaxe baseada em indentação e pontuação simplificada.

Exemplo de `match` com discriminante `trit`:

**0.6:**
```s3
fn sign(value: tryte) -> tryte:
    match value <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
```

## Versões de artefatos

A extensão dos arquivos fonte continua `.s3`. A versão da sintaxe fonte não
altera os formatos posteriores: IR JSON e S3 Assembly permanecem em 0.5.0.

## Próximos Passos (Roadmap)

V0.5 permanece temporariamente disponível para compatibilidade explícita. A
Entrega E e a conclusão do Marco 0.6 continuam pendentes.
