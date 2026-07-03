# Arquitetura do S3 bootstrap 0.2

## Pipeline

```text
fonte
  ↓ lexer posicional
AST explícita (assinaturas, chamadas, switch)
  ↓ semântica em duas fases + retorno por caminhos
IR tipada em blocos
  ↓ verificador obrigatório
S3 Assembly tipada e rotulada
  ↓ parser/validação
emulador com pilha explícita de frames
  ↓
valor de main
```

AST, IR e assembly possuem modelos independentes. A origem atravessa as
fronteiras como `SourceLocation`, não como referência privada à AST.

## Frontend

O parser constrói `FunctionSignature`, `Parameter`, `CallArgument`,
`CallExpression`, `SwitchStatement` e `TernaryCase`. A semântica primeiro
coleta assinaturas e depois analisa corpos, viabilizando forward calls e
recursão direta.

Escopos formam uma pilha. O escopo da função contém parâmetros e locais; cada
caso cria um filho descartado ao final. A análise de bloco retorna um indicador
de terminação definitiva, usado para validar todos os caminhos e código
inalcançável.

## IR e lowering

Cada função começa em `entry`. Um switch produz um `BRANCH3` e três blocos. Se
algum caso continuar, os casos abertos emitem `JUMP` para um bloco de
continuação; se todos retornarem, não há continuação. Isso elimina a necessidade
de `PHI` no subconjunto imutável.

O verificador é separado e executado pelo codegen. A redução de subtração
continua sendo uma invariante estrutural.

## Assembly e emulador

Parâmetros e registradores são declarados no texto; labels preservam os blocos.
O emulador valida o programa inteiro e executa por uma lista Python de objetos
`Frame`, não por recursão Python.

Cada frame contém função, registradores, label atual, índice de instrução,
destino do retorno, bloco/índice de retorno e instrução chamadora. `TCALL`
avança o PC do chamador, copia argumentos a um novo frame e o empilha. `TRET`
remove o frame e escreve no destino salvo.

## Invariantes

1. `-1` nunca é token único.
2. Tipos não sofrem conversão implícita.
3. O seletor de switch e `TBR3` é `trit`.
4. Switch possui exatamente três casos/destinos sem fallthrough.
5. Todo bloco IR/assembly possui exatamente um terminador final.
6. Codegen só consome IR verificada.
7. Registradores são locais ao frame.
8. Toda escrita valida faixa; overflow é erro.
9. Não há `SUBTRACT`/`TSUB`.
10. Python permanece fora do futuro núcleo autohospedado.

## Segurança e riscos conhecidos

Os limites padrão evitam recursão/execução infinita, mas são cotas globais
simples, não um modelo de recursos. O verificador confirma existência e
definição única dos valores, mas ainda não calcula dominância SSA completa;
isso é suficiente sem `PHI` e com o lowering atual, porém deverá evoluir quando
houver joins com valores. A ABI é lógica e será substituída ou traduzida por
uma ABI nativa futura.

