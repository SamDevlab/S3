#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static double sqrt_newton(double value) {
    double estimate = value >= 1.0 ? value : 1.0;
    for (int iteration = 0; iteration < 32; ++iteration) {
        estimate = 0.5 * (estimate + value / estimate);
    }
    return estimate;
}

static double sum_values(const double *values, size_t length) {
    double total = 0.0;
    for (size_t index = 0; index < length; ++index) total += values[index];
    return total;
}

static double mean_values(const double *values, size_t length) {
    return sum_values(values, length) / (double)length;
}

static double sum_squares(const double *values, size_t length) {
    double total = 0.0;
    for (size_t index = 0; index < length; ++index) total += values[index] * values[index];
    return total;
}

static double variance(const double *values, size_t length) {
    const double center = mean_values(values, length);
    double total = 0.0;
    for (size_t index = 0; index < length; ++index) {
        const double delta = values[index] - center;
        total += delta * delta;
    }
    return total / (double)length;
}

static double squared_distance(const double *left, const double *right, size_t length) {
    double total = 0.0;
    for (size_t index = 0; index < length; ++index) {
        const double delta = left[index] - right[index];
        total += delta * delta;
    }
    return total;
}

static double mean_absolute_error(const double *left, const double *right, size_t length) {
    double total = 0.0;
    for (size_t index = 0; index < length; ++index) {
        const double delta = left[index] - right[index];
        total += delta < 0.0 ? -delta : delta;
    }
    return total / (double)length;
}

static double max_absolute(const double *values, size_t length) {
    double maximum = 0.0;
    for (size_t index = 0; index < length; ++index) {
        const double value = values[index] < 0.0 ? -values[index] : values[index];
        if (value > maximum) maximum = value;
    }
    return maximum;
}

static double dot(const double *left, const double *right, size_t length) {
    double total = 0.0;
    for (size_t index = 0; index < length; ++index) total += left[index] * right[index];
    return total;
}

static double norm(const double *values, size_t length) {
    return sqrt_newton(dot(values, values, length));
}

static double covariance(const double *left, const double *right, size_t length) {
    const double leftMean = mean_values(left, length);
    const double rightMean = mean_values(right, length);
    double total = 0.0;
    for (size_t index = 0; index < length; ++index) {
        total += (left[index] - leftMean) * (right[index] - rightMean);
    }
    return total / (double)length;
}

static int64_t score_size(size_t length, size_t seed) {
    static const double pattern[4] = {-1.0, -0.5, 0.5, 1.0};
    double left[8192];
    double right[8192];
    for (size_t index = 0; index < length; ++index) {
        left[index] = pattern[(index + seed) % 4];
        right[index] = left[index] + 0.5;
    }

    const double total = sum_values(left, length);
    const double average = mean_values(left, length);
    const double spread = variance(left, length);
    const double selfProduct = dot(left, left, length);
    const double product = dot(left, right, length);
    const double squared = squared_distance(left, right, length);
    const double euclidean = sqrt_newton(squared);
    const double rmsd = sqrt_newton(squared / (double)length);
    const double magnitude = norm(left, length);
    if (!(-0.01 < total && total < 0.01 && -0.01 < average && average < 0.01 &&
          spread > 0.62 && spread < 0.63 &&
          selfProduct > (double)length * 0.6249 && selfProduct < (double)length * 0.6251 &&
          product > (double)length * 0.6249 && product < (double)length * 0.6251 &&
          squared > (double)length * 0.2499 && squared < (double)length * 0.2501 &&
          euclidean > sqrt_newton((double)length * 0.25) - 0.01 &&
          euclidean < sqrt_newton((double)length * 0.25) + 0.01 &&
          rmsd > 0.49 && rmsd < 0.51 &&
          magnitude > sqrt_newton((double)length * 0.6249) &&
          magnitude < sqrt_newton((double)length * 0.6251))) {
        return -1;
    }

    return (int64_t)length * 5 + 251;
}

static int64_t run_workload(size_t seed) {
    static const size_t lengths[] = {64, 256, 1024, 8192};
    int64_t checksum = 0;
    for (size_t index = 0; index < sizeof(lengths) / sizeof(lengths[0]); ++index) {
        checksum += score_size(lengths[index], seed + index);
    }
    return checksum;
}

int main(int argc, char **argv) {
    if (argc != 3 || strcmp(argv[1], "science.structural-comparison.v1") != 0) {
        fputs("unsupported benchmark invocation\n", stderr);
        return 2;
    }
    char *end = NULL;
    long long loops = strtoll(argv[2], &end, 10);
    if (end == argv[2] || *end != '\0' || loops <= 0) return 2;
    volatile int64_t checksum = 0;
    for (long long loop = 0; loop < loops; ++loop) checksum = run_workload((size_t)loop);
    if (checksum < 0) return 1;
    printf("checksum=%lld\n", (long long)checksum);
    return 0;
}
