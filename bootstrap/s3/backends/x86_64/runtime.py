"""GNU assembly runtime emitted into every standalone S3 executable."""

from __future__ import annotations


ERROR_MESSAGES = {
    "overflow": "runtime error: overflow\n",
    "bounds": "runtime error: bounds\n",
    "uninitialized_register": "runtime error: uninitialized register\n",
    "uninitialized_memory": "runtime error: uninitialized memory\n",
    "immutable_memory": "runtime error: immutable memory\n",
    "invalid_trit": "runtime error: invalid trit\n",
    "frame_limit": "runtime error: frame limit\n",
    "instruction_limit": "runtime error: instruction limit\n",
    "invalid_runtime_state": "runtime error: invalid runtime state\n",
    "capacity": "runtime error: dynamic buffer capacity\n",
    "allocation": "runtime error: dynamic buffer allocation\n",
    "encoding": "runtime error: invalid UTF-8\n",
    "boundary": "runtime error: invalid UTF-8 boundary\n",
}


def _error_runtime() -> list[str]:
    lines: list[str] = []
    for category, message in ERROR_MESSAGES.items():
        lines.extend(
            (
                f"__s3_fail_{category}:",
                f"    lea rsi, [rip + .L__s3_error_{category}]",
                f"    mov edx, {len(message.encode('ascii'))}",
                "    jmp __s3_fail_message",
            )
        )
    lines.extend(
        (
            "__s3_fail:",
            "__s3_fail_message:",
            "    mov eax, 1",
            "    mov edi, 2",
            "    syscall",
            "    mov eax, 60",
            "    mov edi, 1",
            "    syscall",
            "    ud2",
            "",
            "__s3_fail_value:",
            "    mov r12, rdi",
            "    mov r13, rcx",
            "    mov r14, r8",
            "    mov eax, 1",
            "    mov edi, 2",
            "    syscall",
            "    sub rsp, 64",
            "    lea rsi, [rsp + 64]",
            "    xor r15d, r15d",
            "    mov rax, r12",
            "    test rax, rax",
            "    jne .L__s3_fail_value_nonzero",
            "    dec rsi",
            "    mov byte ptr [rsi], 48",
            "    inc r15",
            "    jmp .L__s3_fail_value_write",
            ".L__s3_fail_value_nonzero:",
            "    xor r9d, r9d",
            "    test rax, rax",
            "    jns .L__s3_fail_value_digits",
            "    mov r9d, 1",
            "    neg rax",
            ".L__s3_fail_value_digits:",
            "    xor edx, edx",
            "    mov r10, 10",
            "    div r10",
            "    add dl, 48",
            "    dec rsi",
            "    mov byte ptr [rsi], dl",
            "    inc r15",
            "    test rax, rax",
            "    jne .L__s3_fail_value_digits",
            "    test r9d, r9d",
            "    je .L__s3_fail_value_write",
            "    dec rsi",
            "    mov byte ptr [rsi], 45",
            "    inc r15",
            ".L__s3_fail_value_write:",
            "    mov eax, 1",
            "    mov edi, 2",
            "    mov rdx, r15",
            "    syscall",
            "    mov eax, 1",
            "    mov edi, 2",
            "    mov rsi, r13",
            "    mov rdx, r14",
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


def _dynamic_runtime() -> list[str]:
    """Return the private descriptor ABI and owned buffer builtins."""

    return r"""
.type __s3_dyn_copy,@function
__s3_dyn_copy:
    test rcx,rcx
    jz .L__s3_dyn_copy_done
.L__s3_dyn_copy_loop:
    mov al,byte ptr [rsi]
    mov byte ptr [rdi],al
    inc rsi
    inc rdi
    dec rcx
    jnz .L__s3_dyn_copy_loop
.L__s3_dyn_copy_done:
    ret

.type __s3_dyn_new,@function
__s3_dyn_new:
    push r12
    mov r12,rdi
    test rdi,rdi
    js __s3_fail_capacity
    add rdi,24
    jc __s3_fail_capacity
    mov rsi,rdi
    xor edi,edi
    mov eax,9
    mov edx,3
    mov r10d,34
    mov r8,-1
    xor r9d,r9d
    syscall
    test rax,rax
    js __s3_fail_allocation
    lea rdx,[rax+24]
    mov qword ptr [rax],rdx
    mov qword ptr [rax+8],0
    mov qword ptr [rax+16],r12
    pop r12
    ret

.type __s3_builtin_bytes_new,@function
__s3_builtin_bytes_new:
    jmp __s3_dyn_new
.type __s3_builtin_text_new,@function
__s3_builtin_text_new:
    jmp __s3_dyn_new

.type __s3_builtin_bytes_len,@function
__s3_builtin_bytes_len:
    mov rax,[rdi]
    mov rax,[rax+8]
    ret
.type __s3_builtin_text_len,@function
__s3_builtin_text_len:
    jmp __s3_builtin_bytes_len
.type __s3_builtin_bytes_capacity,@function
__s3_builtin_bytes_capacity:
    mov rax,[rdi]
    mov rax,[rax+16]
    ret
.type __s3_builtin_text_capacity,@function
__s3_builtin_text_capacity:
    jmp __s3_builtin_bytes_capacity

.type __s3_builtin_bytes_get,@function
__s3_builtin_bytes_get:
    mov r10,[rdi]
    cmp rsi,0
    jl __s3_fail_bounds
    cmp rsi,[r10+8]
    jae __s3_fail_bounds
    mov r11,[r10]
    movzx eax,byte ptr [r11+rsi]
    ret
.type __s3_builtin_bytes_set,@function
__s3_builtin_bytes_set:
    cmp rdx,0
    jl __s3_fail_capacity
    cmp rdx,255
    jg __s3_fail_capacity
    mov r10,[rdi]
    cmp rsi,0
    jl __s3_fail_bounds
    cmp rsi,[r10+8]
    jae __s3_fail_bounds
    mov r11,[r10]
    mov byte ptr [r11+rsi],dl
    xor eax,eax
    ret
.type __s3_builtin_bytes_push,@function
__s3_builtin_bytes_push:
    cmp rsi,0
    jl __s3_fail_capacity
    cmp rsi,255
    jg __s3_fail_capacity
    mov r10,[rdi]
    mov rax,[r10+8]
    cmp rax,[r10+16]
    jae __s3_fail_capacity
    mov r11,[r10]
    mov byte ptr [r11+rax],sil
    inc rax
    mov [r10+8],rax
    xor eax,eax
    ret

.type __s3_dyn_reserve,@function
__s3_dyn_reserve:
    push r12
    push r13
    push r14
    push r15
    mov r12,rdi
    mov r13,[rdi]
    mov r15,[r13+8]
    cmp rsi,r15
    jb __s3_fail_capacity
    cmp rsi,[r13+16]
    jbe .L__s3_dyn_reserve_done
    mov rdi,rsi
    call __s3_dyn_new
    mov r14,rax
    mov rcx,r15
    mov rsi,[r13]
    mov rdi,[r14]
    call __s3_dyn_copy
    mov [r14+8],r15
    mov [r12],r14
    mov rdi,r13
    mov rsi,[r13+16]
    add rsi,24
    mov eax,11
    syscall
.L__s3_dyn_reserve_done:
    xor eax,eax
    pop r15
    pop r14
    pop r13
    pop r12
    ret
.type __s3_builtin_bytes_reserve,@function
__s3_builtin_bytes_reserve:
    jmp __s3_dyn_reserve
.type __s3_builtin_text_reserve,@function
__s3_builtin_text_reserve:
    jmp __s3_dyn_reserve

.type __s3_dyn_clone,@function
__s3_dyn_clone:
    push r12
    push r13
    mov r12,[rdi]
    mov rdi,[r12+16]
    call __s3_dyn_new
    mov r13,rax
    mov rcx,[r12+8]
    mov rsi,[r12]
    mov rdi,[r13]
    call __s3_dyn_copy
    mov rax,[r12+8]
    mov [r13+8],rax
    mov rax,r13
    pop r13
    pop r12
    ret
.type __s3_builtin_bytes_clone,@function
__s3_builtin_bytes_clone:
    jmp __s3_dyn_clone
.type __s3_builtin_text_clone,@function
__s3_builtin_text_clone:
    jmp __s3_dyn_clone
.type __s3_builtin_bytes_from_text,@function
__s3_builtin_bytes_from_text:
    jmp __s3_dyn_clone

.type __s3_dyn_concat,@function
__s3_dyn_concat:
    push r12
    push r13
    push r14
    push r15
    mov r12,[rdi]
    mov r13,[rsi]
    mov r15,[r12+8]
    mov rdi,r15
    add rdi,[r13+8]
    jc __s3_fail_capacity
    call __s3_dyn_new
    mov r14,rax
    mov rcx,r15
    mov rsi,[r12]
    mov rdi,[r14]
    call __s3_dyn_copy
    mov rcx,[r13+8]
    mov rsi,[r13]
    mov rdi,[r14]
    add rdi,r15
    call __s3_dyn_copy
    mov rax,r15
    add rax,[r13+8]
    mov [r14+8],rax
    mov rax,r14
    pop r15
    pop r14
    pop r13
    pop r12
    ret
.type __s3_builtin_bytes_concat,@function
__s3_builtin_bytes_concat:
    jmp __s3_dyn_concat
.type __s3_builtin_text_concat,@function
__s3_builtin_text_concat:
    jmp __s3_dyn_concat

.type __s3_dyn_slice,@function
__s3_dyn_slice:
    push r12
    push r13
    push r14
    push r15
    mov r12,[rdi]
    mov r14,rsi
    mov r15,rdx
    cmp r14,0
    jl __s3_fail_bounds
    cmp r15,r14
    jl __s3_fail_bounds
    cmp r15,[r12+8]
    jg __s3_fail_bounds
    mov rdi,r15
    sub rdi,r14
    call __s3_dyn_new
    mov r13,rax
    mov rcx,r15
    sub rcx,r14
    mov rsi,[r12]
    add rsi,r14
    mov rdi,[r13]
    call __s3_dyn_copy
    mov rax,r15
    sub rax,r14
    mov [r13+8],rax
    mov rax,r13
    pop r15
    pop r14
    pop r13
    pop r12
    ret
.type __s3_builtin_bytes_slice,@function
__s3_builtin_bytes_slice:
    jmp __s3_dyn_slice
.type __s3_dyn_is_boundary,@function
__s3_dyn_is_boundary:
    cmp rsi,0
    je .L__s3_boundary_yes
    cmp rsi,[rdi+8]
    je .L__s3_boundary_yes
    mov rdx,[rdi]
    movzx eax,byte ptr [rdx+rsi]
    and eax,192
    cmp eax,128
    sete al
    movzx eax,al
    xor eax,1
    ret
.L__s3_boundary_yes:
    mov eax,1
    ret
.type __s3_builtin_text_slice,@function
__s3_builtin_text_slice:
    push r12
    push r13
    push r14
    mov r12,rdi
    mov r13,rsi
    mov r14,rdx
    mov r10,[rdi]
    cmp r13,0
    jl __s3_fail_bounds
    cmp r14,r13
    jl __s3_fail_bounds
    cmp r14,[r10+8]
    jg __s3_fail_bounds
    mov rdi,r10
    mov rsi,r13
    call __s3_dyn_is_boundary
    test eax,eax
    jz __s3_fail_boundary
    mov rdi,r10
    mov rsi,r14
    call __s3_dyn_is_boundary
    test eax,eax
    jz __s3_fail_boundary
    mov rdi,r12
    mov rsi,r13
    mov rdx,r14
    pop r14
    pop r13
    pop r12
    jmp __s3_dyn_slice

.type __s3_builtin_text_from_static,@function
__s3_builtin_text_from_static:
    push r12
    push r13
    push r14
    mov r12,rdi
    xor r13d,r13d
.L__s3_dyn_strlen:
    cmp byte ptr [r12+r13],0
    je .L__s3_dyn_strlen_done
    inc r13
    jmp .L__s3_dyn_strlen
.L__s3_dyn_strlen_done:
    mov rdi,r13
    call __s3_dyn_new
    mov r14,rax
    mov rdx,[r14]
    mov rcx,r13
    mov rsi,r12
    mov rdi,rdx
    call __s3_dyn_copy
    mov [r14+8],r13
    mov rax,r14
    pop r14
    pop r13
    pop r12
    ret

.type __s3_builtin_text_append,@function
__s3_builtin_text_append:
    push r12
    push r13
    push r14
    push r15
    mov r12,[rdi]
    mov r13,[rsi]
    mov r14,[r12+8]
    mov r15,[r13+8]
    mov rax,r14
    add rax,r15
    jc __s3_fail_capacity
    cmp rax,[r12+16]
    ja __s3_fail_capacity
    mov rcx,r15
    mov rsi,[r13]
    mov rdi,[r12]
    add rdi,r14
    call __s3_dyn_copy
    add r14,r15
    mov [r12+8],r14
    xor eax,eax
    pop r15
    pop r14
    pop r13
    pop r12
    ret
.type __s3_builtin_text_append_static,@function
__s3_builtin_text_append_static:
    push r12
    push r13
    push r14
    push r15
    mov r12,[rdi]
    mov r13,rsi
    mov r14,[r12+8]
    xor rsi,rsi
.L__s3_dyn_append_strlen:
    cmp byte ptr [r13+rsi],0
    je .L__s3_dyn_append_strlen_done
    inc rsi
    jmp .L__s3_dyn_append_strlen
.L__s3_dyn_append_strlen_done:
    mov rax,r14
    add rax,rsi
    jc __s3_fail_capacity
    cmp rax,[r12+16]
    ja __s3_fail_capacity
    mov r15,rax
    mov rcx,rsi
    mov rsi,r13
    mov rdi,[r12]
    add rdi,r14
    call __s3_dyn_copy
    mov [r12+8],r15
    xor eax,eax
    pop r15
    pop r14
    pop r13
    pop r12
    ret

.type __s3_dyn_utf8_valid,@function
__s3_dyn_utf8_valid:
    mov r10,rdi
    lea r11,[rdi+rsi]
.L__s3_utf8_loop:
    cmp r10,r11
    jae .L__s3_utf8_yes
    movzx eax,byte ptr [r10]
    mov r9d,eax
    cmp eax,128
    jb .L__s3_utf8_one
    cmp eax,194
    jb .L__s3_utf8_no
    cmp eax,223
    jbe .L__s3_utf8_two
    cmp eax,239
    jbe .L__s3_utf8_three
    cmp eax,244
    jbe .L__s3_utf8_four
    jmp .L__s3_utf8_no
.L__s3_utf8_one:
    inc r10
    jmp .L__s3_utf8_loop
.L__s3_utf8_two:
    add r10,2
    cmp r10,r11
    ja .L__s3_utf8_no
    movzx eax,byte ptr [r10-1]
    and eax,192
    cmp eax,128
    jne .L__s3_utf8_no
    cmp r9d,224
    jne .L__s3_utf8_three_not_e0
    movzx eax,byte ptr [r10-2]
    cmp eax,160
    jb .L__s3_utf8_no
.L__s3_utf8_three_not_e0:
    cmp r9d,237
    jne .L__s3_utf8_three_done
    movzx eax,byte ptr [r10-2]
    cmp eax,159
    ja .L__s3_utf8_no
.L__s3_utf8_three_done:
    jmp .L__s3_utf8_loop
.L__s3_utf8_three:
    add r10,3
    cmp r10,r11
    ja .L__s3_utf8_no
    movzx eax,byte ptr [r10-2]
    and eax,192
    cmp eax,128
    jne .L__s3_utf8_no
    movzx eax,byte ptr [r10-1]
    and eax,192
    cmp eax,128
    jne .L__s3_utf8_no
    cmp r9d,240
    jne .L__s3_utf8_four_not_f0
    movzx eax,byte ptr [r10-3]
    cmp eax,144
    jb .L__s3_utf8_no
.L__s3_utf8_four_not_f0:
    cmp r9d,244
    jne .L__s3_utf8_four_done
    movzx eax,byte ptr [r10-3]
    cmp eax,143
    ja .L__s3_utf8_no
.L__s3_utf8_four_done:
    jmp .L__s3_utf8_loop
.L__s3_utf8_four:
    add r10,4
    cmp r10,r11
    ja .L__s3_utf8_no
    movzx eax,byte ptr [r10-3]
    and eax,192
    cmp eax,128
    jne .L__s3_utf8_no
    movzx eax,byte ptr [r10-2]
    and eax,192
    cmp eax,128
    jne .L__s3_utf8_no
    movzx eax,byte ptr [r10-1]
    and eax,192
    cmp eax,128
    jne .L__s3_utf8_no
    jmp .L__s3_utf8_loop
.L__s3_utf8_yes:
    mov eax,1
    ret
.L__s3_utf8_no:
    xor eax,eax
    ret
.type __s3_builtin_text_from_bytes,@function
__s3_builtin_text_from_bytes:
    push r12
    push r14
    mov r12,[rdi]
    mov rdi,[r12]
    mov rsi,[r12+8]
    call __s3_dyn_utf8_valid
    test eax,eax
    jz __s3_fail_encoding
    mov rdi,[r12+16]
    call __s3_dyn_new
    mov r14,rax
    mov rcx,[r12+8]
    mov rsi,[r12]
    mov rdx,rcx
    mov rdi,[r14]
    call __s3_dyn_copy
    mov [r14+8],rdx
    mov rax,r14
    pop r14
    pop r12
    ret

.type __s3_builtin_text_find,@function
__s3_builtin_text_find:
    push r12
    push r13
    push r14
    push r15
    mov r12,[rdi]
    mov r13,[r12+8]
    mov r14,[rsi]
    mov r15,[r14+8]
    test r15,r15
    jz .L__s3_find_zero
    cmp r15,r13
    ja .L__s3_find_no
    xor r8d,r8d
.L__s3_find_outer:
    mov rax,r13
    sub rax,r15
    cmp r8,rax
    ja .L__s3_find_no
    mov rdi,[r12]
    add rdi,r8
    mov rsi,[r14]
    mov rcx,r15
    repe cmpsb
    je .L__s3_find_yes
    inc r8
    jmp .L__s3_find_outer
.L__s3_find_zero:
    xor eax,eax
    jmp .L__s3_find_done
.L__s3_find_yes:
    mov rax,r8
    jmp .L__s3_find_done
.L__s3_find_no:
    mov rax,-1
.L__s3_find_done:
    pop r15
    pop r14
    pop r13
    pop r12
    ret
""".strip("\n").splitlines()


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
        *_dynamic_runtime(),
        "",
        *_error_runtime(),
        "",
        ".section .rodata",
        ".L__s3_result_prefix:",
        f'    .ascii "{prefix}"',
        *_error_data(),
        "",
        ".section .bss",
        "    .align 8",
        "__s3_frame_count:",
        "    .zero 8",
        "    .align 8",
        "__s3_instruction_count:",
        "    .zero 8",
        "",
        '.section .note.GNU-stack,"",@progbits',
    ]
    return "\n".join(lines) + "\n"
