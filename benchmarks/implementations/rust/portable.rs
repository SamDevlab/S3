use std::env;

fn scalar_accumulate() -> i64 { 10 + 20 + 12 }

fn check_state(value: i64) -> i64 {
    if value < 0 { 10 } else if value == 0 { 20 } else { 30 }
}

fn branch_state_machine() -> i64 {
    if check_state(1) + check_state(5) == 60 { 1 } else { 0 }
}

fn call_a() -> i64 { 1 }
fn call_b() -> i64 { call_a() + 1 }
fn call_c() -> i64 { call_b() + 1 }
fn call_d() -> i64 { call_c() + 1 }
fn call_e() -> i64 { call_d() + 1 }
fn call_chain() -> i64 { call_e() + call_e() }

fn bounded_recursion(value: i64) -> i64 {
    if value <= 1 { value } else { bounded_recursion(value - 1) + bounded_recursion(value - 2) }
}

fn array_sum() -> i64 {
    [10_i64, 20, 30].iter().copied().sum()
}

fn array_copy() -> i64 {
    let source = [1_i64, 2, 3, 4, 5];
    let copied = source;
    copied.iter().copied().sum()
}

fn bounded_text_scan() -> i64 {
    b"identifier_0123456789"
        .iter()
        .filter(|unit| unit.is_ascii_alphanumeric() || **unit == b'_')
        .count() as i64
}

fn run_workload(benchmark_id: &str) -> Option<i64> {
    match benchmark_id {
        "runtime.scalar.accumulate.v1" => Some(scalar_accumulate()),
        "runtime.scalar.branch.v1" => Some(branch_state_machine()),
        "runtime.call.chain.v1" => Some(call_chain()),
        "runtime.recursion.bounded.v1" => Some(bounded_recursion(10)),
        "runtime.array.sum.tryte.v1" => Some(array_sum()),
        "runtime.array.copy.tryte.v1" => Some(array_copy()),
        "runtime.text.scan.v1" => Some(bounded_text_scan()),
        _ => None,
    }
}

fn main() {
    let arguments: Vec<String> = env::args().collect();
    if arguments.len() != 3 {
        eprintln!("usage: portable <benchmark-id> <loops>");
        std::process::exit(2);
    }
    let loops: u64 = arguments[2].parse().unwrap_or(0);
    if loops == 0 { std::process::exit(2); }
    let mut checksum = 0_i64;
    for _ in 0..loops {
        checksum = run_workload(&arguments[1]).unwrap_or_else(|| std::process::exit(2));
        std::hint::black_box(checksum);
    }
    println!("checksum={checksum}");
}
