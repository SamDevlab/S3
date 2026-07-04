# ADR-0005: modelo de memória lógica do bootstrap

- Status: aceito
- Data: 2026-07-03

## Contexto

O Marco 0.3 precisa introduzir mutabilidade e arrays sem expor ponteiros, heap,
aliasing ou uma ABI física prematura. A escolha não pode derivar
automaticamente do fato de a aritmética S3 ser ternária balanceada: valores
assinados e endereços são problemas arquiteturais distintos.

## Alternativas avaliadas

### Memória endereçada por trits físicos

É conceitualmente próxima de hardware ternário, mas exige decidir packing,
barramento, alinhamento e endereços físicos antes de existir backend. `tryte`
atravessaria seis posições e a validação seria cara no bootstrap.

### Células lógicas tipadas

Uma célula armazenaria um `trit` ou `tryte`. É simples e segura, mas isoladamente
não modela identidade, comprimento e bounds de arrays.

### Objetos tipados com índices

Cada objeto possui identificador, tipo escalar e comprimento fixo. Acesso usa
índice `tryte` validado. Essa alternativa representa escalares mutáveis e
arrays uniformemente, impede aliasing e mantém um caminho claro para baixar
objetos a stack slots/endereço-base em backends futuros.

### Endereçamento bruto por `tryte`

Seria compacto, porém a faixa assinada é inadequada como decisão automática de
endereço, exporia aritmética de ponteiros e limitaria artificialmente memória.
Foi rejeitado neste marco.

## Decisão

Adotar objetos de memória tipados e indexados, locais ao frame:

- unidade endereçável da linguagem: um elemento escalar tipado;
- `trit`: tamanho lógico de 1 trit e alinhamento lógico 1;
- `tryte`: tamanho lógico de 6 trits e alinhamento lógico 6;
- objetos são independentes; não há padding ou endereço observável;
- um tryte é conceitualmente armazenado em seis trits, menos significativo
  primeiro, conforme `spec/ternary.md`;
- arrays armazenam elementos contíguos em ordem crescente de índice;
- cada objeto tem no máximo 365 elementos, pois índices `tryte` válidos para
  memória são `0..364`;
- limite padrão por frame: 2187 trits lógicos (`3^7`), configurável;
- todos os elementos começam não inicializados;
- leitura não inicializada e índice negativo/fora do limite são erros;
- cada chamada aloca objetos próprios e os descarta ao retornar;
- não existe compartilhamento ou aliasing entre objetos/frames.

Objetos imutáveis podem receber exatamente a primeira inicialização de cada
elemento; nova escrita é erro. Objetos mutáveis aceitam escritas posteriores.

## Consequências

Bounds e inicialização são verificáveis sem `IndexError` ou valores
indeterminados. O custo é manter metadados por objeto/elemento no emulador.
Endereços, tamanho físico, endian de bytes, padding e ABI permanecem abstratos.
Um backend futuro poderá mapear objeto para stack slot ou região, preservando
tipo, comprimento e checks, e só então definir ponteiros.
