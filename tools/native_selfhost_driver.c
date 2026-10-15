#define _GNU_SOURCE

#include <errno.h>
#include <dlfcn.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/types.h>

#if !defined(__linux__) || !defined(__x86_64__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "the S3C-NG native transport driver requires Linux x86-64"
#endif

#define MAX_DYNAMIC_BYTES (64ULL * 1024ULL * 1024ULL)
#define MAX_SOURCE_UNITS 4096U
#define INPUT_MAGIC "S3NGIN01"
#define OUTPUT_MAGIC "S3NGOUT1"
#define OUTPUT_V2_MAGIC "S3NGOUT2"
#define DIAGNOSTIC_RECORD_I64S 7U
#define MAX_DIAGNOSTIC_RECORDS 256U

typedef struct {
    unsigned char *data;
    int64_t length;
    int64_t capacity;
} S3DynamicDescriptor;

typedef struct {
    S3DynamicDescriptor *path;
    S3DynamicDescriptor *contents;
} NgSourceUnit;

_Static_assert(sizeof(S3DynamicDescriptor) == 24, "S3 dynamic descriptor ABI changed");
_Static_assert(sizeof(NgSourceUnit) == 16, "NgSourceUnit ABI changed");

typedef int64_t (*NgSourceSetCompiler)(
    void **units_reference,
    void *entry_module,
    void **source_reference,
    void **events_reference
);

typedef int64_t (*NgSourceSetCompilerV2)(
    void **units_reference,
    void *entry_module,
    void **source_reference,
    void **events_reference,
    void **diagnostics_reference
);

static int fail(const char *message) {
    fprintf(stderr, "native S3C-NG transport: %s\n", message);
    return 2;
}

static int has_suffix(const char *value, const char *suffix) {
    size_t value_length = strlen(value);
    size_t suffix_length = strlen(suffix);
    return value_length >= suffix_length &&
        strcmp(value + value_length - suffix_length, suffix) == 0;
}

static int read_exact(FILE *stream, void *destination, size_t length) {
    unsigned char *cursor = destination;
    while (length != 0) {
        size_t count = fread(cursor, 1, length, stream);
        if (count == 0) {
            return 0;
        }
        cursor += count;
        length -= count;
    }
    return 1;
}

static int write_exact(FILE *stream, const void *source, size_t length) {
    const unsigned char *cursor = source;
    while (length != 0) {
        size_t count = fwrite(cursor, 1, length, stream);
        if (count == 0) {
            return 0;
        }
        cursor += count;
        length -= count;
    }
    return 1;
}

static S3DynamicDescriptor *dynamic_new(
    uint64_t capacity,
    const unsigned char *contents,
    uint64_t length
) {
    if (capacity > MAX_DYNAMIC_BYTES || length > capacity || capacity > SIZE_MAX - 24) {
        return NULL;
    }
    size_t allocation_size = (size_t)capacity + 24;
    S3DynamicDescriptor *descriptor = mmap(
        NULL,
        allocation_size,
        PROT_READ | PROT_WRITE,
        MAP_PRIVATE | MAP_ANONYMOUS,
        -1,
        0
    );
    if (descriptor == MAP_FAILED) {
        return NULL;
    }
    descriptor->data = (unsigned char *)(descriptor + 1);
    descriptor->length = (int64_t)length;
    descriptor->capacity = (int64_t)capacity;
    if (length != 0 && contents != NULL) {
        memcpy(descriptor->data, contents, (size_t)length);
    }
    return descriptor;
}

static int read_u32(FILE *stream, uint32_t *value) {
    return read_exact(stream, value, sizeof(*value));
}

static int read_u64(FILE *stream, uint64_t *value) {
    return read_exact(stream, value, sizeof(*value));
}

static unsigned char *read_blob(FILE *stream, uint64_t length) {
    if (length > MAX_DYNAMIC_BYTES || length > SIZE_MAX) {
        return NULL;
    }
    size_t allocation_size = length == 0 ? 1 : (size_t)length;
    unsigned char *contents = malloc(allocation_size);
    if (contents == NULL || !read_exact(stream, contents, (size_t)length)) {
        free(contents);
        return NULL;
    }
    return contents;
}

static int write_output(
    const char *path,
    int64_t status,
    const S3DynamicDescriptor *source,
    const S3DynamicDescriptor *events
) {
    if (source == NULL || events == NULL || source->length < 0 || events->length < 0 ||
        (events->length % (int64_t)sizeof(int64_t)) != 0 ||
        (uint64_t)source->length > (uint64_t)source->capacity ||
        (uint64_t)events->length > (uint64_t)events->capacity) {
        return 0;
    }
    uint64_t source_length = (uint64_t)source->length;
    uint64_t event_count = (uint64_t)events->length / sizeof(int64_t);
    FILE *stream = fopen(path, "wb");
    if (stream == NULL) {
        return 0;
    }
    int ok = write_exact(stream, OUTPUT_MAGIC, 8) &&
        write_exact(stream, &status, sizeof(status)) &&
        write_exact(stream, &source_length, sizeof(source_length)) &&
        write_exact(stream, &event_count, sizeof(event_count)) &&
        write_exact(stream, source->data, (size_t)source_length) &&
        write_exact(stream, events->data, (size_t)(event_count * sizeof(int64_t)));
    if (fclose(stream) != 0) {
        ok = 0;
    }
    return ok;
}

static int write_output_v2(
    const char *path,
    int64_t status,
    const S3DynamicDescriptor *source,
    const S3DynamicDescriptor *events,
    const S3DynamicDescriptor *diagnostics
) {
    const uint64_t diagnostic_record_bytes = DIAGNOSTIC_RECORD_I64S * sizeof(int64_t);
    if (source == NULL || events == NULL || diagnostics == NULL ||
        source->length < 0 || events->length < 0 || diagnostics->length < 0 ||
        (events->length % (int64_t)sizeof(int64_t)) != 0 ||
        (diagnostics->length % (int64_t)diagnostic_record_bytes) != 0 ||
        (uint64_t)source->length > (uint64_t)source->capacity ||
        (uint64_t)events->length > (uint64_t)events->capacity ||
        (uint64_t)diagnostics->length > (uint64_t)diagnostics->capacity) {
        return 0;
    }
    uint64_t source_length = (uint64_t)source->length;
    uint64_t event_count = (uint64_t)events->length / sizeof(int64_t);
    uint64_t diagnostic_count = (uint64_t)diagnostics->length / diagnostic_record_bytes;
    if (diagnostic_count > MAX_DIAGNOSTIC_RECORDS) {
        return 0;
    }
    FILE *stream = fopen(path, "wb");
    if (stream == NULL) {
        return 0;
    }
    int ok = write_exact(stream, OUTPUT_V2_MAGIC, 8) &&
        write_exact(stream, &status, sizeof(status)) &&
        write_exact(stream, &source_length, sizeof(source_length)) &&
        write_exact(stream, &event_count, sizeof(event_count)) &&
        write_exact(stream, &diagnostic_count, sizeof(diagnostic_count)) &&
        write_exact(stream, source->data, (size_t)source_length) &&
        write_exact(stream, events->data, (size_t)(event_count * sizeof(int64_t))) &&
        write_exact(stream, diagnostics->data, (size_t)(diagnostic_count * diagnostic_record_bytes));
    if (fclose(stream) != 0) {
        ok = 0;
    }
    return ok;
}

int main(int argc, char **argv) {
    if (argc != 4) {
        return fail("expected entry-symbol, input-manifest, and output-envelope");
    }
    dlerror();
    NgSourceSetCompiler compiler = (NgSourceSetCompiler)dlsym(RTLD_DEFAULT, argv[1]);
    const char *symbol_error = dlerror();
    if (symbol_error != NULL || compiler == NULL) {
        fprintf(stderr, "native S3C-NG transport: entry symbol: %s\n",
                symbol_error == NULL ? "not found" : symbol_error);
        return 2;
    }

    FILE *manifest = fopen(argv[2], "rb");
    if (manifest == NULL) {
        perror("native S3C-NG transport: open manifest");
        return 2;
    }

    char magic[8];
    uint32_t entry_length = 0;
    uint32_t unit_count = 0;
    if (!read_exact(manifest, magic, sizeof(magic)) ||
        memcmp(magic, INPUT_MAGIC, sizeof(magic)) != 0 ||
        !read_u32(manifest, &entry_length) ||
        !read_u32(manifest, &unit_count) ||
        unit_count == 0 || unit_count > MAX_SOURCE_UNITS) {
        fclose(manifest);
        return fail("invalid source manifest header");
    }

    unsigned char *entry_bytes = read_blob(manifest, entry_length);
    if (entry_bytes == NULL) {
        fclose(manifest);
        return fail("could not read entry-module field");
    }
    S3DynamicDescriptor *entry_module = dynamic_new(entry_length, entry_bytes, entry_length);
    free(entry_bytes);
    if (entry_module == NULL) {
        fclose(manifest);
        return fail("could not allocate entry-module descriptor");
    }

    if ((uint64_t)unit_count > MAX_DYNAMIC_BYTES / sizeof(NgSourceUnit)) {
        fclose(manifest);
        return fail("source-unit vector exceeds runtime capacity");
    }
    uint64_t units_bytes = (uint64_t)unit_count * sizeof(NgSourceUnit);
    S3DynamicDescriptor *units = dynamic_new(units_bytes, NULL, units_bytes);
    if (units == NULL) {
        fclose(manifest);
        return fail("could not allocate source-unit vector");
    }

    uint64_t total_input_bytes = 0;
    NgSourceUnit *unit_data = (NgSourceUnit *)units->data;
    for (uint32_t index = 0; index < unit_count; ++index) {
        uint32_t path_length = 0;
        uint64_t contents_length = 0;
        if (!read_u32(manifest, &path_length) || !read_u64(manifest, &contents_length)) {
            fclose(manifest);
            return fail("truncated source-unit metadata");
        }
        unsigned char *path_bytes = read_blob(manifest, path_length);
        unsigned char *contents_bytes = read_blob(manifest, contents_length);
        if (path_bytes == NULL || contents_bytes == NULL) {
            free(path_bytes);
            free(contents_bytes);
            fclose(manifest);
            return fail("could not read source-unit bytes");
        }
        unit_data[index].path = dynamic_new(path_length, path_bytes, path_length);
        unit_data[index].contents = dynamic_new(contents_length, contents_bytes, contents_length);
        free(path_bytes);
        free(contents_bytes);
        if (unit_data[index].path == NULL || unit_data[index].contents == NULL) {
            fclose(manifest);
            return fail("could not allocate source-unit descriptors");
        }
        if (total_input_bytes > MAX_DYNAMIC_BYTES - path_length ||
            total_input_bytes + path_length > MAX_DYNAMIC_BYTES - contents_length) {
            fclose(manifest);
            return fail("source manifest exceeds runtime input bound");
        }
        total_input_bytes += path_length + contents_length;
    }
    int trailing = fgetc(manifest);
    if (fclose(manifest) != 0 || trailing != EOF) {
        return fail("source manifest has trailing bytes or could not close");
    }

    uint64_t source_capacity = total_input_bytes + 8192;
    if (source_capacity < 32768) {
        source_capacity = 32768;
    }
    if (source_capacity > MAX_DYNAMIC_BYTES) {
        source_capacity = MAX_DYNAMIC_BYTES;
    }
    S3DynamicDescriptor *source = dynamic_new(source_capacity, NULL, 0);
    S3DynamicDescriptor *events = dynamic_new(MAX_DYNAMIC_BYTES, NULL, 0);
    if (source == NULL || events == NULL) {
        return fail("could not allocate compiler output descriptors");
    }

    void *units_value = units;
    void *source_value = source;
    void *events_value = events;
    int is_v2 = has_suffix(argv[1], "ng_emit_source_set_v2");
    int64_t status = 0;
    int output_ok = 0;
    if (is_v2) {
        uint64_t diagnostic_capacity =
            MAX_DIAGNOSTIC_RECORDS * DIAGNOSTIC_RECORD_I64S * sizeof(int64_t);
        S3DynamicDescriptor *diagnostics = dynamic_new(diagnostic_capacity, NULL, 0);
        if (diagnostics == NULL) {
            return fail("could not allocate diagnostic output descriptor");
        }
        void *diagnostics_value = diagnostics;
        NgSourceSetCompilerV2 compiler_v2 = (NgSourceSetCompilerV2)compiler;
        status = compiler_v2(
            &units_value,
            entry_module,
            &source_value,
            &events_value,
            &diagnostics_value
        );
        output_ok = write_output_v2(
            argv[3],
            status,
            (const S3DynamicDescriptor *)source_value,
            (const S3DynamicDescriptor *)events_value,
            (const S3DynamicDescriptor *)diagnostics_value
        );
    } else {
        status = compiler(
            &units_value,
            entry_module,
            &source_value,
            &events_value
        );
        output_ok = write_output(
            argv[3],
            status,
            (const S3DynamicDescriptor *)source_value,
            (const S3DynamicDescriptor *)events_value
        );
    }
    if (!output_ok) {
        return fail("could not write compiler output envelope");
    }
    return 0;
}
