# ADR-0009: artefatos versionados e reprodutibilidade

- Status: aceito
- Data: 2026-07-03

## Contexto

IR e S3 Assembly deixaram de ser apenas detalhes de depuração: são fronteiras
entre compilador, ferramentas, emulador e backend. Sem versão explícita, uma
mudança incompatível pode ser aceita com interpretação errada. Sem forma
canônica, diffs, caches e builds reproduzíveis perdem utilidade.

## Decisão

Os artefatos atuais usam versão `0.5.0`.

S3 Assembly textual começa por:

```asm
.s3asm 0.5.0
```

O renderer sempre emite o cabeçalho. O parser aceita `0.5.0` e, por
compatibilidade, assembly 0.1–0.4 sem cabeçalho; legado é normalizado em memória
para o modelo atual e renderizado como 0.5.0. Cabeçalho malformado, versão
desconhecida ou major incompatível são erros. Não há aceitação silenciosa de
versões futuras.

A IR persistente usa JSON UTF-8:

```json
{
  "format": "s3-ir",
  "version": "0.5.0",
  "module": {
    "functions": []
  }
}
```

O JSON é independente de `repr`, possui chaves ordenadas, indentação de dois
espaços e newline final. Todos os campos semânticos e origens são explícitos.
Desserialização valida envelope e tipos, reconstrói dataclasses e executa o
verificador; não existe `pickle` nem execução de dados.

Compatibilidade dentro de 0.5 exige leitura exata do formato conhecido. Uma
futura versão ganha migração deliberada; major novo é incompatível por padrão.
A política conservadora privilegia erro explícito sobre interpretação parcial.

## Reprodutibilidade

Há dois contratos:

1. mesma estrutura produz o mesmo S3 Assembly e IR JSON byte a byte;
2. mesma entrada, configuração, versão de driver/assembler/linker e opções
   produz o mesmo ELF byte a byte.

O link desativa build ID automático. Texto não inclui timestamps, caminhos
temporários ou IDs aleatórios. Builds em diretórios diferentes são comparados
por SHA-256. GCC versus Clang, versões diferentes ou linkers diferentes exigem
equivalência semântica, não identidade binária.

## Consequências

Ferramentas podem rejeitar artefatos incompatíveis cedo e usar conteúdo como
chave de cache. O custo é manter leitores/migrações explícitos. O compilador
continua livre para evoluir seus modelos internos, desde que converta pela
fronteira versionada.

