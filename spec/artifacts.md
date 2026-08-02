# Artefatos persistentes S3 0.6

Status: normativo.

## Versões

Escritores atuais de S3 Assembly e S3 IR JSON usam `0.6.0`. Leitores aceitam
`0.5.0` como legado escalar width-1 e o normalizam para os campos explícitos de
0.6.0. Versão ausente só é permitida para assembly legado 0.1–0.4. Versão
desconhecida, futura ou malformada é erro.

## S3 Assembly

O primeiro item significativo é:

```asm
.s3asm 0.6.0
```

Linhas vazias anteriores são toleradas na leitura, mas o renderer canônico
começa diretamente pelo cabeçalho. Legado 0.5 width-1 é normalizado e volta a
ser emitido com cabeçalho atual. Formas 0.6.0 de grupos de resultados sob
header 0.5 são rejeitadas.

## S3 IR JSON

Envelope:

```json
{
  "format": "s3-ir",
  "version": "0.6.0",
  "module": {
    "functions": []
  }
}
```

Funções contêm assinatura, parâmetros, registros, objetos de memória, blocos e
instruções. Cada função contém `result_types`, e cada instrução produtora contém
`results`; `return_type` e `result` continuam presentes apenas para a fronteira
width-1. Origem usa `{offset, line, column}` ou `null`. Referências de
registro/memória usam índices inteiros no formato persistente. Todos os campos
obrigatórios são validados e campos desconhecidos são rejeitados para impedir
erros de digitação silenciosos.

Serialização canônica é JSON UTF-8, `ensure_ascii=false`, chaves
lexicograficamente ordenadas, indentação de dois espaços e newline final.
Round-trip deve preservar igualdade estrutural e passar `verify_ir`.

## Reprodutibilidade

Texto canônico é idêntico em qualquer host. ELF só promete identidade com a
mesma entrada, configuração e toolchain. `--build-id=none`, ordem estável e
ausência de timestamps/paths variáveis são obrigatórios.

