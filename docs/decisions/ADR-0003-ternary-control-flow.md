# ADR-0003: controle de fluxo ternário exaustivo

- Status: aceito
- Data: 2026-07-03

## Contexto

S3 precisa expressar decisão sem reduzir seu domínio nativo a booleanos
binários. Comparações já produzem `-1`, `0` ou `1`, mas um controle parcial
criaria comportamento implícito para um dos estados.

## Decisão

Introduzir `switch (expressão)` restrito a `trit`, com casos obrigatórios e
únicos `-1`, `0`, `1`. Não há `default` nem fallthrough. O seletor é avaliado
uma vez e cada caso possui bloco e escopo próprios.

Na IR, `BRANCH3 condition, negative, neutral, positive` é terminador com três
destinos explícitos e distintos. Na assembly, `TBR3` preserva a mesma ordem.

## Justificativa

- exigir `trit` conecta comparação e controle sem coerção;
- os três casos obrigatórios tornam a análise total e evitam estado ignorado;
- `default` ocultaria qual estado deixou de ser tratado;
- fallthrough introduziria ordem acidental e dificultaria retorno por caminhos;
- três arestas explícitas são mapeáveis tanto a hardware ternário futuro quanto
  a backends binários.

## Alternativas consideradas

- `if/else` binário: não representa o estado neutro como cidadão de primeira
  classe.
- casos opcionais com `default`: mais familiar, porém menos verificável.
- fallthrough estilo C: compacto em alguns casos, mas incompatível com os
  escopos independentes e a semântica total desejada.

## Consequências

Switches são verbosos, mas exaustivos. Um switch cujos três casos retornam é
terminador; caso contrário, ramos abertos saltam a uma continuação. Como nomes
de caso não escapam, o Marco 0.2 não necessita de `PHI`.

