# ADR-0006: mutabilidade explícita e lowering para memória

- Status: aceito
- Data: 2026-07-03

## Contexto

Bindings S3 0.2 são imutáveis e valores da IR têm definição única. A comunicação
de um valor produzido em ramos diferentes exigiria `PHI`; arrays também
necessitam estado. O Marco 0.3 deve resolver ambos sem abandonar SSA para
valores puros.

## Decisão

Bindings continuam imutáveis por padrão. `mut` habilita atribuição explícita:

```s3
mut tryte value = 0;
value = 1;
```

O lowering mantém escalares imutáveis em registradores SSA. Somente escalares
mutáveis e todos os arrays recebem `IRMemoryObject`:

- declaração cria objeto e armazena o inicializador;
- leitura de mutável/indexação emite `LOAD`;
- atribuição emite `STORE`;
- escalares mutáveis usam objeto de comprimento 1 e índice constante 0;
- arrays usam um objeto com o comprimento declarado;
- cada índice e valor continua sendo registrador SSA.

Uma variável mutável declarada antes de `BRANCH3` pode ser armazenada em cada
ramo e carregada no join. A identidade do objeto domina conceitualmente a
função, então nenhum `PHI` é necessário. Bindings imutáveis não são
materializados em memória sem necessidade.

## Inicialização

Na IR, `STORE` carrega um marcador explícito de inicialização. O verificador
permite esse marcador em objetos imutáveis e rejeita escrita comum neles. Na
assembly, `TSTORE` inicializa uma célula imutável apenas quando ela ainda está
vazia; a segunda escrita é erro dinâmico. O frontend sempre inicializa todas as
declarações.

## Alternativas consideradas

- tornar todas as variáveis mutáveis: quebraria contratos 0.1/0.2;
- manter mutáveis em registradores e inserir `PHI`: amplia a IR e a análise;
- colocar todos os bindings em memória: simples, mas degrada SSA e mascara
  distinções importantes;
- promover memória automaticamente: otimização prematura.

## Consequências e limitações

O modelo é explícito, seguro e preserva SSA para a maioria dos valores. Há mais
`CONST 0`, `LOAD` e `STORE`, e o emulador precisa rastrear inicialização.
Arrays não podem ser copiados, passados ou retornados. Promoção de memória para
SSA poderá ser implementada no futuro após dominância e `PHI` estarem maduros.

