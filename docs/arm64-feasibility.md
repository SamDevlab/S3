# Viabilidade de backend Linux ARM64

Status: estudo do Marco 0.5; ARM64 não é suportado.

## ABI e frames

AArch64 ELF normalmente usa AAPCS64: oito argumentos inteiros em `x0`–`x7`,
retorno em `x0`, excedentes na pilha e `sp` alinhado a 16 bytes. `x29` pode
servir de frame pointer e `x30` contém o link register. O layout lógico atual
— slots virtuais, flags e objetos locais — pode ser reutilizado, mas offsets e
prólogo/epílogo precisam de cálculo próprio; não se deve traduzir literalmente
o emitter AMD64.

## Representação

`trit` int8, `tryte` int16 e temporários int64 continuam viáveis. Loads exigem
extensão de sinal (`ldrsb`/`ldrsh`). Arrays permanecem contíguos. Checks de
faixa, bounds, inicialização, imutabilidade e contador privado de frames não
dependem conceitualmente de x86-64.

## Runtime

Linux AArch64 usa a instrução `svc 0` e números de syscall diferentes dos
x86-64; `write`/`exit`, conversão decimal, diagnósticos contextuais e helpers
tritwise precisam de implementação assembly própria. `_start` deve respeitar o
estado inicial de `sp` e não pode depender de libc.

Tritwise min/max podem decompor seis dígitos por divisão assinada, mas
instruções, registradores preservados e custo diferem. Vale avaliar uma rotina
compartilhada em representação intermediária somente depois que ambos os
backends existirem; compartilhar texto assembly seria incorreto.

## Toolchain e CI

São necessários GNU binutils/GCC ou Clang para target AArch64 e validação real
de ELF. Opções:

- runner Linux ARM64 nativo, preferível para testes de execução;
- cross-assembler/linker mais QEMU user-mode;
- runner x86-64 apenas para montagem/inspeção, insuficiente para concluir
  suporte.

A CI deve executar todos os exemplos, erros, recursão, O0/O1,
reprodutibilidade e `readelf`, sem skips silenciosos. QEMU acrescenta risco de
diferenças de sinal/syscall e deve ser complementado por execução nativa antes
de declarar estabilidade.

## Riscos e esforço

- immediates e offsets limitados exigem materialização adicional;
- link register torna chamadas/recursão diferentes;
- toolchains cross podem introduzir metadados não reproduzíveis;
- diagnóstico por site aumenta alcance de labels/literais;
- QEMU pode esconder problemas de alinhamento ou kernel;
- duas ABIs aumentam a matriz de manutenção.

Trabalho estimado: ADR físico/ABI próprio, módulo de layout, emitter completo,
runtime, descoberta de toolchain, corpus diferencial e job ARM64 obrigatório.
Nenhum arquivo ou comando ARM64 é criado no 0.5; o roadmap não o marca como
suportado.

