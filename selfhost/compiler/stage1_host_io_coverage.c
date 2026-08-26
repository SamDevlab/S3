#include <stdint.h>

enum { STAGE1_MAX_SOURCE_BYTES = 262144 };

static unsigned char stage1_source[STAGE1_MAX_SOURCE_BYTES];
static unsigned char stage1_source_touched[STAGE1_MAX_SOURCE_BYTES];
static int64_t stage1_source_length = -1;
static int64_t stage1_max_read_index = -1;

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

static void stage1_error_bytes(const char *text) {
    const char *cursor = text;
    while (*cursor != '\0') {
        stage1_syscall3(
            1,
            2,
            (int64_t)(uintptr_t)cursor,
            1
        );
        cursor += 1;
    }
}

static void stage1_error_decimal(int64_t value) {
    char digits[32];
    int64_t used = 0;
    uint64_t magnitude;

    if (value < 0) {
        stage1_error_bytes("-");
        magnitude = (uint64_t)(-(value + 1)) + 1;
    } else {
        magnitude = (uint64_t)value;
    }
    if (magnitude == 0) {
        stage1_error_bytes("0");
        return;
    }
    while (magnitude > 0) {
        digits[used] = (char)('0' + (magnitude % 10));
        magnitude /= 10;
        used += 1;
    }
    while (used > 0) {
        used -= 1;
        stage1_syscall3(
            1,
            2,
            (int64_t)(uintptr_t)&digits[used],
            1
        );
    }
}

static void stage1_emit_coverage(void) {
    int64_t length = stage1_load_source();
    int64_t touched = 0;
    int64_t first_unread = -1;
    int64_t index = 0;
    int64_t bounded_length = length;

    if (bounded_length > STAGE1_MAX_SOURCE_BYTES) {
        bounded_length = STAGE1_MAX_SOURCE_BYTES;
    }
    while (index < bounded_length) {
        if (stage1_source_touched[index] != 0) {
            touched += 1;
        } else if (first_unread < 0) {
            first_unread = index;
        }
        index += 1;
    }

    stage1_error_bytes("S3_STAGE1_COVERAGE length=");
    stage1_error_decimal(length);
    stage1_error_bytes(" touched=");
    stage1_error_decimal(touched);
    stage1_error_bytes(" first_unread=");
    stage1_error_decimal(first_unread);
    stage1_error_bytes(" max_read=");
    stage1_error_decimal(stage1_max_read_index);
    stage1_error_bytes("\n");
}

int64_t s3_stage1_source_length(void) {
    return stage1_load_source();
}

int64_t s3_stage1_read_byte(int64_t index) {
    int64_t length = stage1_load_source();
    if (index < 0 || index >= length) {
        return -1;
    }
    if (index < STAGE1_MAX_SOURCE_BYTES) {
        stage1_source_touched[index] = 1;
        if (index > stage1_max_read_index) {
            stage1_max_read_index = index;
        }
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
    stage1_emit_coverage();
    stage1_syscall3(60, status, 0, 0);
    return status;
}
