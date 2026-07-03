# Roadmap do S3

## Marco 0.1 — fatia vertical bootstrap (concluído)

- modelo de `trit`/`tryte`, frontend inicial e semântica;
- lowering sem subtração;
- IR/assembly lineares e emulador;
- overflow detectável, CLI, testes e especificação.

## Marco 0.2 — funções e controle ternário (concluído)

- parâmetros, múltiplas funções, forward calls e recursão;
- resolução em duas fases e diagnósticos de chamada;
- `switch` exaustivo sobre `trit`, escopos de caso e retorno por caminhos;
- IR em blocos com `CALL`, `JUMP`, `BRANCH3` e origem;
- verificador estrutural obrigatório;
- assembly com `.param`, `.label`, `TCALL`, `TJMP` e `TBR3`;
- ABI lógica e emulador com frames explícitos;
- limites configuráveis de frames/instruções;
- round-trip textual e exemplos ponta a ponta.

## Marco 0.3 — memória e agregados mínimos (recomendado)

1. definir unidade endereçável e espaço de endereços assinado;
2. especificar layout e alinhamento de trits/trytes;
3. adicionar carga, armazenamento e alocação de frame;
4. introduzir mutabilidade explícita sem comportamento indefinido;
5. definir agregados mínimos, inicialmente arrays de tamanho estático;
6. estender análise de fluxo e dominância da IR;
7. criar testes de isolamento, limites e segurança de memória.

Antes de implementar, o modelo de memória deve receber ADR próprio. Ponteiros
arbitrários, I/O e ABI nativa continuam fora desse marco inicial.

## Marco 0.4 — backend nativo experimental

- verificador de IR com dominância completa;
- seleção x86-64 e depois ARM64;
- representação binária de trits;
- testes diferenciais contra o emulador.

## Marco 0.5 — autohospedagem incremental

- assembler e frontend escritos no subconjunto S3;
- compilação reprodutível em estágios;
- retirada gradual de Python do caminho de produção.

## Questões abertas

ABI física, encoding binário, layout de memória, otimizações, linker e
microarquitetura ternária ainda não são contratos. Cada escolha exige
especificação, ADR e testes.

