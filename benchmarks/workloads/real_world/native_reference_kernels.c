#include <math.h>
#include <stdint.h>

int64_t point_cloud_summary(
    const double *coordinates,
    int64_t coordinate_count,
    int64_t point_count,
    double *output,
    int64_t output_count
) {
    if (point_count <= 0 || point_count > 121) return 1;
    if (coordinate_count != point_count * 3 || output_count != 10) return 2;

    double minimum_x = coordinates[0];
    double minimum_y = coordinates[1];
    double minimum_z = coordinates[2];
    double maximum_x = minimum_x;
    double maximum_y = minimum_y;
    double maximum_z = minimum_z;
    double total_x = 0.0;
    double total_y = 0.0;
    double total_z = 0.0;

    for (int64_t point = 0; point < point_count; ++point) {
        const int64_t base = point * 3;
        const double x = coordinates[base];
        const double y = coordinates[base + 1];
        const double z = coordinates[base + 2];
        total_x += x;
        total_y += y;
        total_z += z;
        if (x < minimum_x) minimum_x = x;
        if (y < minimum_y) minimum_y = y;
        if (z < minimum_z) minimum_z = z;
        if (x > maximum_x) maximum_x = x;
        if (y > maximum_y) maximum_y = y;
        if (z > maximum_z) maximum_z = z;
    }

    const double center_x = total_x / (double)point_count;
    const double center_y = total_y / (double)point_count;
    const double center_z = total_z / (double)point_count;
    double squared_radius_sum = 0.0;
    for (int64_t point = 0; point < point_count; ++point) {
        const int64_t base = point * 3;
        const double dx = coordinates[base] - center_x;
        const double dy = coordinates[base + 1] - center_y;
        const double dz = coordinates[base + 2] - center_z;
        squared_radius_sum += dx * dx + dy * dy + dz * dz;
    }

    output[0] = center_x;
    output[1] = center_y;
    output[2] = center_z;
    output[3] = minimum_x;
    output[4] = minimum_y;
    output[5] = minimum_z;
    output[6] = maximum_x;
    output[7] = maximum_y;
    output[8] = maximum_z;
    output[9] = sqrt(squared_radius_sum / (double)point_count);
    return 0;
}

int64_t raster_window_statistics(
    const double *values,
    int64_t value_count,
    const int64_t *valid_mask,
    int64_t mask_count,
    int64_t width,
    int64_t height,
    double threshold,
    double *output,
    int64_t output_count
) {
    if (width <= 0 || height <= 0 || width > 364 || height > 364) return 1;
    const int64_t cell_count = width * height;
    if (cell_count > 364) return 1;
    if (value_count != cell_count || mask_count != cell_count || output_count != 6) return 2;

    int64_t valid_count = 0;
    int64_t gradient_count = 0;
    int64_t threshold_count = 0;
    double total = 0.0;
    double minimum = 0.0;
    double maximum = 0.0;
    double gradient_total = 0.0;
    for (int64_t row = 0; row < height; ++row) {
        for (int64_t column = 0; column < width; ++column) {
            const int64_t index = row * width + column;
            if (valid_mask[index] != 1) continue;
            const double value = values[index];
            if (valid_count == 0) {
                minimum = value;
                maximum = value;
            }
            ++valid_count;
            total += value;
            if (value > threshold) ++threshold_count;
            if (value < minimum) minimum = value;
            if (value > maximum) maximum = value;
            if (column + 1 < width && valid_mask[index + 1] == 1) {
                gradient_total += fabs(values[index + 1] - value);
                ++gradient_count;
            }
        }
    }
    if (valid_count <= 0 || gradient_count <= 0) return 3;
    output[0] = total;
    output[1] = total / (double)valid_count;
    output[2] = minimum;
    output[3] = maximum;
    output[4] = (double)threshold_count;
    output[5] = gradient_total / (double)gradient_count;
    return 0;
}

int64_t energy_series_aggregation(
    const double *ac_power,
    int64_t ac_count,
    const double *load,
    int64_t load_count,
    double capacity_w,
    double *output,
    int64_t output_count
) {
    if (ac_count <= 0 || ac_count > 364 || capacity_w <= 0.0) return 1;
    if (load_count != ac_count || output_count != 5) return 2;

    double ac_energy = 0.0;
    double net_energy = 0.0;
    double peak = ac_power[0];
    double absolute_balance = 0.0;
    for (int64_t period = 0; period < ac_count; ++period) {
        const double ac = ac_power[period];
        ac_energy += ac;
        net_energy = net_energy + ac - load[period];
        absolute_balance += fabs(ac - load[period]);
        if (ac > peak) peak = ac;
    }
    output[0] = ac_energy;
    output[1] = peak;
    output[2] = net_energy;
    output[3] = ac_energy / (capacity_w * (double)ac_count);
    output[4] = absolute_balance / (double)ac_count;
    return 0;
}
