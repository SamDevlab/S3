const std = @import("std");

fn sum(values: []const f64) f64 {
    var total: f64 = 0.0;
    for (values) |value| total += value;
    return total;
}

fn mean(values: []const f64) f64 {
    const total = sum(values);
    return total / @as(f64, @floatFromInt(values.len));
}

fn sumSquares(values: []const f64) f64 {
    var total: f64 = 0.0;
    for (values) |value| total += value * value;
    return total;
}

fn variance(values: []const f64) f64 {
    const center = mean(values);
    var total: f64 = 0.0;
    for (values) |value| {
        const delta = value - center;
        total += delta * delta;
    }
    return total / @as(f64, @floatFromInt(values.len));
}

fn squaredDistance(left: []const f64, right: []const f64) f64 {
    var total: f64 = 0.0;
    for (left, right) |a, b| {
        const delta = a - b;
        total += delta * delta;
    }
    return total;
}

fn meanAbsoluteError(left: []const f64, right: []const f64) f64 {
    var total: f64 = 0.0;
    for (left, right) |a, b| total += @abs(a - b);
    return total / @as(f64, @floatFromInt(left.len));
}

fn maxAbsolute(values: []const f64) f64 {
    var maximum: f64 = 0.0;
    for (values) |value| maximum = @max(maximum, @abs(value));
    return maximum;
}

fn dot(left: []const f64, right: []const f64) f64 {
    var total: f64 = 0.0;
    for (left, right) |a, b| total += a * b;
    return total;
}

fn norm(values: []const f64) f64 {
    return @sqrt(dot(values, values));
}

fn covariance(left: []const f64, right: []const f64) f64 {
    const leftMean = mean(left);
    const rightMean = mean(right);
    var total: f64 = 0.0;
    for (left, right) |a, b| total += (a - leftMean) * (b - rightMean);
    return total / @as(f64, @floatFromInt(left.len));
}

fn scoreSize(length: usize, seed: usize) i64 {
    const pattern = [_]f64{ -1.0, -0.5, 0.5, 1.0 };
    var left: [8192]f64 = undefined;
    var right: [8192]f64 = undefined;
    var index: usize = 0;
    while (index < length) : (index += 1) {
        left[index] = pattern[(index + seed) % 4];
        right[index] = left[index] + 0.5;
    }

    const leftValues = left[0..length];
    const rightValues = right[0..length];
    const total = sum(leftValues);
    const average = mean(leftValues);
    const spread = variance(leftValues);
    const selfProduct = dot(leftValues, leftValues);
    const product = dot(leftValues, rightValues);
    const squared = squaredDistance(leftValues, rightValues);
    const euclidean = @sqrt(squared);
    const rmsd = @sqrt(squared / @as(f64, @floatFromInt(length)));
    const magnitude = norm(leftValues);
    const lengthF64 = @as(f64, @floatFromInt(length));
    if (!(-0.01 < total and total < 0.01 and -0.01 < average and average < 0.01 and
        spread > 0.62 and spread < 0.63 and
        selfProduct > lengthF64 * 0.6249 and selfProduct < lengthF64 * 0.6251 and
        product > lengthF64 * 0.6249 and product < lengthF64 * 0.6251 and
        squared > lengthF64 * 0.2499 and squared < lengthF64 * 0.2501 and
        @abs(euclidean - @sqrt(lengthF64 * 0.25)) < 0.01 and
        rmsd > 0.49 and rmsd < 0.51 and
        magnitude > @sqrt(lengthF64 * 0.6249) and
        magnitude < @sqrt(lengthF64 * 0.6251))) return -1;

    return @as(i64, @intCast(length)) * 5 + 251;
}

fn runWorkload(seed: usize) i64 {
    return scoreSize(64, seed) + scoreSize(256, seed + 1) + scoreSize(1024, seed + 2) + scoreSize(8192, seed + 3);
}

pub fn main() !void {
    var arguments = std.process.args();
    _ = arguments.next();
    const benchmarkId = arguments.next() orelse return error.InvalidArguments;
    if (!std.mem.eql(u8, benchmarkId, "science.structural-comparison.v1")) return error.InvalidArguments;
    const loopsText = arguments.next() orelse return error.InvalidArguments;
    if (arguments.next() != null) return error.InvalidArguments;
    const loops = try std.fmt.parseInt(u64, loopsText, 10);
    if (loops == 0) return error.InvalidArguments;
    var checksum: i64 = 0;
    var loop: u64 = 0;
    while (loop < loops) : (loop += 1) {
        checksum = runWorkload(@as(usize, @intCast(loop)));
        std.mem.doNotOptimizeAway(checksum);
    }
    if (checksum < 0) return error.CorrectnessFailure;
    try std.io.getStdOut().writer().print("checksum={d}\n", .{checksum});
}
