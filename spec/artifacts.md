# Artefatos persistentes S3 0.5

Status: normativo.

## Versões

S3 Assembly e S3 IR JSON usam `0.5.0`. Versão ausente só é permitida para
assembly legado 0.1–0.4. Versão desconhecida, futura ou malformada é erro.

## S3 Assembly

O primeiro item significativo é:

```asm
.s3asm 0.5.0
```

Linhas vazias anteriores são toleradas na leitura, mas o renderer canônico
começa diretamente pelo cabeçalho. Legado é normalizado e volta a ser emitido
com cabeçalho atual.

## S3 IR JSON

Envelope:

```json
{
  "format": "s3-ir",
  "version": "0.5.0",
  "module": {
    "functions": []
  }
}
```

Funções contêm assinatura, parâmetros, registros, objetos de memória, blocos e
instruções. Origem usa `{offset, line, column}` ou `null`. Referências de
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

