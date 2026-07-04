"""GNU assembly runtime emitted into every standalone S3 executable."""

from __future__ import annotations


ERROR_MESSAGES = {
    "overflow": "runtime error: overflow\n",
    "bounds": "runtime error: bounds\n",
    "uninitialized_register": "runtime error: uninitialized register\n",
    "uninitialized_memory": "runtime error: uninitialized memory\n",
    "immutable_memory": "runtime error: immutable memory\n",
    "invalid_trit": "runtime error: invalid trit\n",
}


def _error_runtime() -> list[str]:
    lines: list[str] = []
    for category, message in ERROR_MESSAGES.items():
        lines.extend(
            (
                f"__s3_fail_{category}:",
                f"    lea rsi, [rip + .L__s3_error_{category}]",
                f"    mov edx, {len(message.encode('ascii'))}",
                "    jmp __s3_fail",
            )
        )
    lines.extend(
        (
            "__s3_fail:",
            "    mov eax, 1",
            "    mov edi, 2",
            "    syscall",
            "    mov eax, 60",
            "    mov edi, 1",
            "    syscall",
            "    ud2",
        )
    )
    return lines


def _error_data() -> list[str]:
    lines: list[str] = []
    for category, message in ERROR_MESSAGES.items():
        escaped = message.replace("\\", "\\\\").replace("\n", "\\n")
        lines.extend(
            (
                f".L__s3_error_{category}:",
                f'    .ascii "{escaped}"',
            )
        )
    return lines


def render_runtime() -> str:
    """Return deterministic Intel-syntax GNU assembly for the native runtime."""

    prefix = "program returned: "
    lines = [
        ".section .text",
        ".globl _start",
        ".type _start, @function",
        "_start:",
        "    and rsp, -16",
        "    call s3_main",
        "    mov r12, rax",
        "    mov eax, 1",
        "    mov edi, 1",
        "    lea rsi, [rip + .L__s3_result_prefix]",
        f"    mov edx, {len(prefix)}",
        "    syscall",
        "    mov rdi, r12",
        "    call __s3_print_i64",
        "    mov eax, 60",
        "    xor edi, edi",
        "    syscall",
        "    ud2",
        ".size _start, .-_start",
        "",
        ".type __s3_print_i64, @function",
        "__s3_print_i64:",
        "    push rbp",
        "    mov rbp, rsp",
        "    sub rsp, 64",
        "    lea rsi, [rbp - 1]",
        "    mov byte ptr [rsi], 10",
        "    mov r8, 1",
        "    mov rax, rdi",
        "    test rax, rax",
        "    jne .L__s3_print_nonzero",
        "    dec rsi",
        "    mov byte ptr [rsi], 48",
        "    inc r8",
        "    jmp .L__s3_print_write",
        ".L__s3_print_nonzero:",
        "    xor r9d, r9d",
        "    test rax, rax",
        "    jns .L__s3_print_digits",
        "    mov r9d, 1",
        "    neg rax",
        ".L__s3_print_digits:",
        "    xor edx, edx",
        "    mov r10, 10",
        "    div r10",
        "    add dl, 48",
        "    dec rsi",
        "    mov byte ptr [rsi], dl",
        "    inc r8",
        "    test rax, rax",
        "    jne .L__s3_print_digits",
        "    test r9d, r9d",
        "    je .L__s3_print_write",
        "    dec rsi",
        "    mov byte ptr [rsi], 45",
        "    inc r8",
        ".L__s3_print_write:",
        "    mov eax, 1",
        "    mov edi, 1",
        "    mov rdx, r8",
        "    syscall",
        "    leave",
        "    ret",
        ".size __s3_print_i64, .-__s3_print_i64",
        "",
        ".type __s3_tryte_min, @function",
        "__s3_tryte_min:",
        "    xor r11d, r11d",
        "    jmp .L__s3_tryte_extreme",
        ".size __s3_tryte_min, .-__s3_tryte_min",
        "",
        ".type __s3_tryte_max, @function",
        "__s3_tryte_max:",
        "    mov r11d, 1",
        ".L__s3_tryte_extreme:",
        "    push r12",
        "    push r13",
        "    push r14",
        "    push r15",
        "    mov r12, rdi",
        "    mov r13, rsi",
        "    xor r14d, r14d",
        "    mov r15, 1",
        "    mov ecx, 6",
        "    mov r10, 3",
        ".L__s3_tryte_digit_loop:",
        "    mov rax, r12",
        "    cqo",
        "    idiv r10",
        "    cmp rdx, 2",
        "    jne .L__s3_tryte_left_negative_two",
        "    mov rdx, -1",
        "    inc rax",
        "    jmp .L__s3_tryte_left_ready",
        ".L__s3_tryte_left_negative_two:",
        "    cmp rdx, -2",
        "    jne .L__s3_tryte_left_ready",
        "    mov rdx, 1",
        "    dec rax",
        ".L__s3_tryte_left_ready:",
        "    mov r12, rax",
        "    mov r8, rdx",
        "    mov rax, r13",
        "    cqo",
        "    idiv r10",
        "    cmp rdx, 2",
        "    jne .L__s3_tryte_right_negative_two",
        "    mov rdx, -1",
        "    inc rax",
        "    jmp .L__s3_tryte_right_ready",
        ".L__s3_tryte_right_negative_two:",
        "    cmp rdx, -2",
        "    jne .L__s3_tryte_right_ready",
        "    mov rdx, 1",
        "    dec rax",
        ".L__s3_tryte_right_ready:",
        "    mov r13, rax",
        "    mov r9, rdx",
        "    test r11d, r11d",
        "    jne .L__s3_tryte_select_max",
        "    cmp r8, r9",
        "    cmovg r8, r9",
        "    jmp .L__s3_tryte_selected",
        ".L__s3_tryte_select_max:",
        "    cmp r8, r9",
        "    cmovl r8, r9",
        ".L__s3_tryte_selected:",
        "    imul r8, r15",
        "    add r14, r8",
        "    imul r15, r15, 3",
        "    dec ecx",
        "    jne .L__s3_tryte_digit_loop",
        "    mov rax, r14",
        "    pop r15",
        "    pop r14",
        "    pop r13",
        "    pop r12",
        "    ret",
        ".size __s3_tryte_max, .-__s3_tryte_max",
        "",
        *_error_runtime(),
        "",
        ".section .rodata",
        ".L__s3_result_prefix:",
        f'    .ascii "{prefix}"',
        *_error_data(),
        "",
        '.section .note.GNU-stack,"",@progbits',
    ]
    return "\n".join(lines) + "\n"

