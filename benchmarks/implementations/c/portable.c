#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int64_t scalar_accumulate(void) {
    int64_t a = 10;
    int64_t b = 20;
    return a + b + 12;
}

static int64_t check_state(int64_t value) {
    if (value < 0) return 10;
    if (value == 0) return 20;
    return 30;
}

static int64_t branch_state_machine(void) {
    return check_state(1) + check_state(5) == 60 ? 1 : 0;
}

static int64_t call_a(void) { return 1; }
static int64_t call_b(void) { return call_a() + 1; }
static int64_t call_c(void) { return call_b() + 1; }
static int64_t call_d(void) { return call_c() + 1; }
static int64_t call_e(void) { return call_d() + 1; }
static int64_t call_chain(void) { return call_e() + call_e(); }

static int64_t bounded_recursion(int64_t value) {
    if (value <= 1) return value;
    return bounded_recursion(value - 1) + bounded_recursion(value - 2);
}

static int64_t array_sum(void) {
    const int64_t values[3] = {10, 20, 30};
    int64_t total = 0;
    for (size_t index = 0; index < 3; ++index) total += values[index];
    return total;
}

static int64_t array_copy(void) {
    const int64_t source[5] = {1, 2, 3, 4, 5};
    int64_t copied[5];
    int64_t total = 0;
    for (size_t index = 0; index < 5; ++index) copied[index] = source[index];
    for (size_t index = 0; index < 5; ++index) total += copied[index];
    return total;
}

static int64_t bounded_text_scan(void) {
    static const unsigned char text[] = "identifier_0123456789";
    int64_t accepted = 0;
    for (size_t index = 0; index < sizeof(text) - 1; ++index) {
        unsigned char unit = text[index];
        if ((unit >= '0' && unit <= '9') || (unit >= 'A' && unit <= 'Z') ||
            (unit >= 'a' && unit <= 'z') || unit == '_') {
            ++accepted;
        }
    }
    return accepted;
}

static int64_t run_workload(const char *benchmark_id) {
    if (strcmp(benchmark_id, "runtime.scalar.accumulate.v1") == 0) return scalar_accumulate();
    if (strcmp(benchmark_id, "runtime.scalar.branch.v1") == 0) return branch_state_machine();
    if (strcmp(benchmark_id, "runtime.call.chain.v1") == 0) return call_chain();
    if (strcmp(benchmark_id, "runtime.recursion.bounded.v1") == 0) return bounded_recursion(10);
    if (strcmp(benchmark_id, "runtime.array.sum.tryte.v1") == 0) return array_sum();
    if (strcmp(benchmark_id, "runtime.array.copy.tryte.v1") == 0) return array_copy();
    if (strcmp(benchmark_id, "runtime.text.scan.v1") == 0) return bounded_text_scan();
    return INT64_MIN;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fputs("usage: portable <benchmark-id> <loops>\n", stderr);
        return 2;
    }
    char *end = NULL;
    long long loops = strtoll(argv[2], &end, 10);
    if (end == argv[2] || *end != '\0' || loops <= 0) return 2;
    volatile int64_t checksum = 0;
    for (long long loop = 0; loop < loops; ++loop) checksum = run_workload(argv[1]);
    if (checksum == INT64_MIN) return 2;
    printf("checksum=%lld\n", (long long)checksum);
    return 0;
}
