const std = @import("std");

fn scalarAccumulate() i64 { return 10 + 20 + 12; }

fn checkState(value: i64) i64 {
    if (value < 0) return 10;
    if (value == 0) return 20;
    return 30;
}

fn branchStateMachine() i64 {
    return if (checkState(1) + checkState(5) == 60) 1 else 0;
}

fn callA() i64 { return 1; }
fn callB() i64 { return callA() + 1; }
fn callC() i64 { return callB() + 1; }
fn callD() i64 { return callC() + 1; }
fn callE() i64 { return callD() + 1; }
fn callChain() i64 { return callE() + callE(); }

fn boundedRecursion(value: i64) i64 {
    if (value <= 1) return value;
    return boundedRecursion(value - 1) + boundedRecursion(value - 2);
}

fn arraySum() i64 {
    const values = [_]i64{ 10, 20, 30 };
    var total: i64 = 0;
    for (values) |value| total += value;
    return total;
}

fn arrayCopy() i64 {
    const source = [_]i64{ 1, 2, 3, 4, 5 };
    const copied = source;
    var total: i64 = 0;
    for (copied) |value| total += value;
    return total;
}

fn boundedTextScan() i64 {
    const text = "identifier_0123456789";
    var accepted: i64 = 0;
    for (text) |unit| {
        if (std.ascii.isAlphanumeric(unit) or unit == '_') accepted += 1;
    }
    return accepted;
}

fn runWorkload(benchmark_id: []const u8) ?i64 {
    if (std.mem.eql(u8, benchmark_id, "runtime.scalar.accumulate.v1")) return scalarAccumulate();
    if (std.mem.eql(u8, benchmark_id, "runtime.scalar.branch.v1")) return branchStateMachine();
    if (std.mem.eql(u8, benchmark_id, "runtime.call.chain.v1")) return callChain();
    if (std.mem.eql(u8, benchmark_id, "runtime.recursion.bounded.v1")) return boundedRecursion(10);
    if (std.mem.eql(u8, benchmark_id, "runtime.array.sum.tryte.v1")) return arraySum();
    if (std.mem.eql(u8, benchmark_id, "runtime.array.copy.tryte.v1")) return arrayCopy();
    if (std.mem.eql(u8, benchmark_id, "runtime.text.scan.v1")) return boundedTextScan();
    return null;
}

pub fn main() !void {
    var arguments = std.process.args();
    _ = arguments.next();
    const benchmark_id = arguments.next() orelse return error.InvalidArguments;
    const loops_text = arguments.next() orelse return error.InvalidArguments;
    if (arguments.next() != null) return error.InvalidArguments;
    const loops = try std.fmt.parseInt(u64, loops_text, 10);
    if (loops == 0) return error.InvalidArguments;
    var checksum: i64 = 0;
    var loop: u64 = 0;
    while (loop < loops) : (loop += 1) {
        checksum = runWorkload(benchmark_id) orelse return error.InvalidArguments;
        std.mem.doNotOptimizeAway(checksum);
    }
    try std.io.getStdOut().writer().print("checksum={d}\n", .{checksum});
}
