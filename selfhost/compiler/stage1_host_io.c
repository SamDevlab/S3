#include <stdint.h>

enum { STAGE1_MAX_SOURCE_BYTES = 262144 };

static unsigned char stage1_source[STAGE1_MAX_SOURCE_BYTES];
static int64_t stage1_source_length = -1;

static int64_t stage1_syscall3(
    int64_t number,
    int64_t first,
    int64_t second,
    int64_t third
) {
    int64_t result;
    __asm__ volatile(
        "syscall"
        : "=a"(result)
        : "a"(number), "D"(first), "S"(second), "d"(third)
        : "rcx", "r11", "memory"
    );
    return result;
}

static int64_t stage1_load_source(void) {
    int64_t count = 0;
    if (stage1_source_length >= 0) {
        return stage1_source_length;
    }
    while (count < STAGE1_MAX_SOURCE_BYTES) {
        int64_t received = stage1_syscall3(
            0,
            0,
            (int64_t)(uintptr_t)(stage1_source + count),
            STAGE1_MAX_SOURCE_BYTES - count
        );
        if (received <= 0) {
            break;
        }
        count += received;
    }
    if (count == STAGE1_MAX_SOURCE_BYTES) {
        unsigned char probe = 0;
        int64_t received = stage1_syscall3(
            0,
            0,
            (int64_t)(uintptr_t)&probe,
            1
        );
        stage1_source_length = received > 0
            ? STAGE1_MAX_SOURCE_BYTES + 1
            : STAGE1_MAX_SOURCE_BYTES;
    } else {
        stage1_source_length = count;
    }
    return stage1_source_length;
}

int64_t s3_stage1_source_length(void) {
    return stage1_load_source();
}

int64_t s3_stage1_read_byte(int64_t index) {
    int64_t length = stage1_load_source();
    if (index < 0 || index >= length) {
        return -1;
    }
    return stage1_source[index];
}

int64_t s3_stage1_write_byte(int64_t value) {
    unsigned char byte = (unsigned char)value;
    stage1_syscall3(1, 1, (int64_t)(uintptr_t)&byte, 1);
    return 0;
}

int64_t s3_stage1_write_error_byte(int64_t value) {
    unsigned char byte = (unsigned char)value;
    stage1_syscall3(1, 2, (int64_t)(uintptr_t)&byte, 1);
    return 0;
}

int64_t s3_stage1_exit(int64_t status) {
    stage1_syscall3(60, status, 0, 0);
    return status;
}
