# ADR-0004: convenção lógica de chamadas do bootstrap

- Status: aceito
- Data: 2026-07-03

## Contexto

Chamadas aninhadas e recursivas exigem isolamento, retorno ao ponto correto e
limites contra execução infinita. Ainda não existe memória, pilha física ou ABI
de máquina.

## Decisão

Adotar uma ABI lógica baseada em frames:

- cada função declara parâmetros ordenados com `.param`;
- `TCALL dest, function, args...` avalia/copia argumentos por valor;
- cada chamada cria registradores locais inicialmente contendo só parâmetros;
- o frame guarda função, bloco, PC, destino, bloco/PC de retorno e chamada;
- o PC do chamador avança antes do novo frame ser empilhado;
- `TRET source` remove o frame e copia o valor a `dest` do chamador;
- chamadas aninhadas e recursivas usam frames independentes;
- terminar bloco/função sem terminador/`TRET` é erro;
- `main` não recebe parâmetros.

O emulador usa uma pilha explícita, não recursão Python. Os limites padrão são
1024 frames simultâneos e 100.000 instruções executadas; ambos são configuráveis
e excedê-los gera diagnóstico.

## Alternativas consideradas

- recursão nativa Python: simples, mas mistura limites do hospedeiro à máquina
  S3 e dificulta inspeção.
- registradores globais: menores, porém quebram chamadas aninhadas e recursão.
- pilha física/ABI x86-64: prematura sem memória e backend.
- registradores caller/callee-saved: desnecessários enquanto cada frame possui
  namespace próprio.

## Consequências

A ABI textual é determinística e suficiente para testar recursão. Ela não
prescreve stack pointer, alinhamento, endereço físico de retorno, passagem em
registradores nativos ou interoperabilidade. Um backend futuro deverá traduzir
esta semântica para sua ABI e poderá adotar convenções diferentes sem alterar o
comportamento observável S3.

