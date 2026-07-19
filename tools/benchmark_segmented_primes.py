import argparse
import concurrent.futures
import importlib.util
import json
import math
import multiprocessing
import os
import platform
import subprocess
import sys
import time
from pathlib import Path


def simple_sieve(limit):
    if limit < 2:
        return 0, None, None, 0
    sieve = bytearray([1]) * (limit + 1)
    sieve[0] = sieve[1] = 0
    for p in range(2, int(limit**0.5) + 1):
        if sieve[p]:
            for i in range(p * p, limit + 1, p):
                sieve[i] = 0
    count = 0
    first = None
    last = None
    checksum = 0
    for p in range(2, limit + 1):
        if sieve[p]:
            count += 1
            if first is None:
                first = p
            last = p
            checksum += p
    return count, first, last, checksum


def get_base_primes(limit):
    sqrt_limit = int(limit**0.5)
    if sqrt_limit < 2:
        return []
    sieve = bytearray([1]) * (sqrt_limit + 1)
    sieve[0] = sieve[1] = 0
    for p in range(2, int(sqrt_limit**0.5) + 1):
        if sieve[p]:
            for i in range(p * p, sqrt_limit + 1, p):
                sieve[i] = 0
    return [p for p in range(2, sqrt_limit + 1) if sieve[p]]


def process_segment(args):
    k, segment_bytes, limit, base_primes = args
    low = k * segment_bytes * 2
    high = min(low + segment_bytes * 2 - 1, limit)
    if low >= limit:
        return 0, None, None, 0

    max_odd = high if high % 2 != 0 else high - 1
    if max_odd < low + 1:
        if low == 0 and limit >= 2:
            return 1, 2, 2, 2
        return 0, None, None, 0

    num_odds = (max_odd - (low + 1)) // 2 + 1
    sieve = bytearray([1]) * num_odds

    if low == 0:
        sieve[0] = 0  # 1 is not prime

    for p in base_primes:
        if p == 2:
            continue
        start = p * p
        if start < low:
            start = ((low + p - 1) // p) * p
            if start % 2 == 0:
                start += p

        if start <= max_odd:
            start_idx = (start - (low + 1)) // 2
            for i in range(start_idx, num_odds, p):
                sieve[i] = 0

    count = 0
    first = None
    last = None
    checksum = 0

    if low == 0 and limit >= 2:
        count += 1
        first = 2
        last = 2
        checksum += 2

    for i in range(num_odds):
        if sieve[i]:
            p = low + 1 + 2 * i
            count += 1
            if first is None or (first == 2 and count == 2):
                if first is None or first == 2:
                    if first == 2 and count > 1:
                        pass
                    else:
                        first = p
            last = p
            checksum += p

    return count, first, last, checksum


def segmented_sieve_sequential(limit, segment_bytes):
    if limit < 2:
        return 0, None, None, 0
    base = get_base_primes(limit)
    total_count = 0
    first = None
    last = None
    total_checksum = 0

    num_segments = (limit + segment_bytes * 2 - 1) // (segment_bytes * 2)
    for k in range(num_segments):
        c, f, l, s = process_segment((k, segment_bytes, limit, base))
        total_count += c
        total_checksum += s
        if f is not None and first is None:
            first = f
        if l is not None:
            last = l
    return total_count, first, last, total_checksum


def segmented_sieve_parallel(limit, segment_bytes, workers):
    if limit < 2:
        return 0, None, None, 0
    base = get_base_primes(limit)
    total_count = 0
    first = None
    last = None
    total_checksum = 0

    num_segments = (limit + segment_bytes * 2 - 1) // (segment_bytes * 2)
    args_list = [(k, segment_bytes, limit, base) for k in range(num_segments)]

    if workers == 1:
        results = [process_segment(arg) for arg in args_list]
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(process_segment, args_list))

    for c, f, l, s in results:
        total_count += c
        total_checksum += s
        if f is not None and first is None:
            first = f
        if l is not None:
            last = l
    return total_count, first, last, total_checksum


def _get_machine_profile():
    profile = {
        "os": platform.system(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "physical_cpus": None,
        "ram_capacity": None,
        "cpu_name": platform.processor(),
    }
    
    if platform.system() == "Windows":
        try:
            res = subprocess.run(
                ["powershell", "-Command", "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors | ConvertTo-Json"],
                capture_output=True, text=True
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, list): data = data[0]
                profile["cpu_name"] = data.get("Name", profile["cpu_name"])
                profile["physical_cpus"] = data.get("NumberOfCores")
                profile["logical_cpus"] = data.get("NumberOfLogicalProcessors")
            
            res_ram = subprocess.run(
                ["powershell", "-Command", "Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum | Select-Object Sum | ConvertTo-Json"],
                capture_output=True, text=True
            )
            if res_ram.returncode == 0 and res_ram.stdout.strip():
                data = json.loads(res_ram.stdout)
                profile["ram_capacity"] = data.get("Sum")
        except Exception:
            pass

    return profile


def run_benchmark_cycle(algo_func, args, warmups, runs):
    for _ in range(warmups):
        algo_func(*args)
    
    times = []
    for _ in range(runs):
        start = time.perf_counter_ns()
        res = algo_func(*args)
        end = time.perf_counter_ns()
        times.append(end - start)
    
    times.sort()
    median_ns = times[len(times) // 2]
    return median_ns, res


def verify():
    limits = [10, 100, 1000, 1000000]
    expected_counts = {10: 4, 100: 25, 1000: 168, 1000000: 78498}
    print("Verification:")
    for limit in limits:
        print(f"Limit: {limit}")
        c1, f1, l1, s1 = simple_sieve(limit)
        c2, f2, l2, s2 = segmented_sieve_sequential(limit, 32768)
        c3, f3, l3, s3 = segmented_sieve_parallel(limit, 32768, 2)
        
        ok = True
        if not (c1 == c2 == c3 == expected_counts.get(limit, c1)):
            print(f"  Count mismatch: {c1}, {c2}, {c3}")
            ok = False
        if not (f1 == f2 == f3):
            print(f"  First mismatch: {f1}, {f2}, {f3}")
            ok = False
        if not (l1 == l2 == l3):
            print(f"  Last mismatch: {l1}, {l2}, {l3}")
            ok = False
        if not (s1 == s2 == s3):
            print(f"  Checksum mismatch: {s1}, {s2}, {s3}")
            ok = False
            
        if ok:
            print("  [OK]")
        else:
            print("  [FAIL]")
            sys.exit(1)


def quick():
    print("Quick Benchmark:")
    limit = 10_000_000
    segment_bytes = 65536
    workers = min(os.cpu_count() or 1, 4)
    print(f"Limit={limit}, Segment={segment_bytes}B, Workers={workers}")
    
    t_seq, _ = run_benchmark_cycle(segmented_sieve_sequential, (limit, segment_bytes), 1, 3)
    t_par, _ = run_benchmark_cycle(segmented_sieve_parallel, (limit, segment_bytes, workers), 1, 3)
    
    print(f"Seq Median: {t_seq / 1e6:.2f} ms")
    print(f"Par Median: {t_par / 1e6:.2f} ms")
    if t_par > 0:
        print(f"Speedup: {t_seq / t_par:.2f}x")


def tune(segment_bytes_list, workers_list, warmups, runs, output_file):
    limit = 10_000_000
    results = []
    for sb in segment_bytes_list:
        print(f"Tuning segment size {sb} bytes...")
        t_seq, _ = run_benchmark_cycle(segmented_sieve_sequential, (limit, sb), warmups, runs)
        for w in workers_list:
            t_par, _ = run_benchmark_cycle(segmented_sieve_parallel, (limit, sb, w), warmups, runs)
            results.append({
                "segment_bytes": sb,
                "workers": w,
                "median_ns": t_par,
                "speedup_vs_seq": t_seq / t_par if t_par > 0 else 0
            })
            print(f"  Workers={w}, Median={t_par/1e6:.2f}ms, Speedup={t_seq / t_par:.2f}x")
    
    best = min(results, key=lambda x: x["median_ns"])
    print(f"Best configuration: Segment {best['segment_bytes']}B, Workers {best['workers']}")
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump({
                "tune": results,
                "best": best
            }, f, indent=2)


def full(output_file):
    if not os.path.exists(output_file):
        print(f"Need tuning data in {output_file} first.")
        sys.exit(1)
        
    with open(output_file, 'r') as f:
        data = json.load(f)
        
    best = data["best"]
    sb = best["segment_bytes"]
    w = best["workers"]
    
    limits = [1_000_000, 10_000_000, 100_000_000]
    full_results = []
    
    for limit in limits:
        print(f"Benchmarking limit {limit}...")
        if limit <= 10_000_000:
            t_sim, res_sim = run_benchmark_cycle(simple_sieve, (limit,), 2, 5)
        else:
            t_sim, res_sim = -1, None
            
        t_seq, res_seq = run_benchmark_cycle(segmented_sieve_sequential, (limit, sb), 2, 5)
        t_par, res_par = run_benchmark_cycle(segmented_sieve_parallel, (limit, sb, w), 2, 5)
        
        full_results.append({
            "limit": limit,
            "simple_ns": t_sim,
            "seq_ns": t_seq,
            "par_ns": t_par,
            "prime_count": res_seq[0],
            "checksum": res_seq[3]
        })
        
    data["full"] = full_results
    data["profile"] = _get_machine_profile()
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)


def report(input_file):
    with open(input_file, 'r') as f:
        data = json.load(f)
        
    report_path = Path("docs/performance/prime-search-0.34.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    md = [
        "# S3 0.34 Prime Search Benchmark Report",
        "",
        "## Hardware Profile",
        f"- **OS**: {data['profile']['os']}",
        f"- **CPU**: {data['profile']['cpu_name']}",
        f"- **Logical CPUs**: {data['profile']['logical_cpus']}",
        f"- **Physical Cores**: {data['profile']['physical_cpus']}",
        "",
        "## Best Configuration",
        f"- **Segment Size**: {data['best']['segment_bytes']} bytes",
        f"- **Workers**: {data['best']['workers']}",
        "",
        "## Full Benchmark Results",
        "| Limit | Simple Sieve (ms) | Seq Sieve (ms) | Par Sieve (ms) | Speedup | Count |",
        "|---|---|---|---|---|---|"
    ]
    
    for row in data["full"]:
        limit = row["limit"]
        t_sim = f"{row['simple_ns'] / 1e6:.2f}" if row['simple_ns'] > 0 else "N/A"
        t_seq = f"{row['seq_ns'] / 1e6:.2f}"
        t_par = f"{row['par_ns'] / 1e6:.2f}"
        sp = f"{row['seq_ns'] / row['par_ns']:.2f}x" if row['par_ns'] > 0 else "N/A"
        cnt = row["prime_count"]
        md.append(f"| {limit} | {t_sim} | {t_seq} | {t_par} | {sp} | {cnt} |")
        
    with open(report_path, 'w') as f:
        f.write("\n".join(md) + "\n")
    print(f"Report written to {report_path}")


def gpu_probe():
    print("GPU Capability Probe")
    print("--------------------")
    clinfo = subprocess.run(["where.exe", "clinfo"] if platform.system() == "Windows" else ["which", "clinfo"], capture_output=True, text=True)
    if clinfo.returncode == 0:
        print("clinfo: Found")
        res = subprocess.run([clinfo.stdout.strip().split("\n")[0]], capture_output=True, text=True)
        if "Number of devices" in res.stdout:
            print("  OpenCL devices detected.")
    else:
        print("clinfo: Not found")
        
    pyopencl = importlib.util.find_spec('pyopencl')
    print(f"pyopencl: {'Found' if pyopencl else 'Not found (GPU backend unavailable)'}")


def main():
    parser = argparse.ArgumentParser(description="Segmented Prime Search Benchmark")
    parser.add_argument("command", choices=["verify", "quick", "tune", "full", "report", "gpu-probe"])
    parser.add_argument("--segment-bytes", type=str, default="32768,65536,262144,1048576")
    parser.add_argument("--workers", type=str, default="1,2,4,8")
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", type=str, default=".tmp-prime-search-0.34-results.json")
    
    args = parser.parse_args()
    
    if args.command == "verify":
        verify()
    elif args.command == "quick":
        quick()
    elif args.command == "tune":
        sbs = [int(x) for x in args.segment_bytes.split(",")]
        ws = [int(x) for x in args.workers.split(",")]
        tune(sbs, ws, args.warmups, args.runs, args.output)
    elif args.command == "full":
        full(args.output)
    elif args.command == "report":
        report(args.output)
    elif args.command == "gpu-probe":
        gpu_probe()


if __name__ == "__main__":
    main()
