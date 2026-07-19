import argparse
import concurrent.futures
import json
import math
import multiprocessing
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

sys.set_int_max_str_digits(0)

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from tools.segmented_bigint import (
    Base300BigInt, BinaryLimbBigInt,
    square_segment, combine_segments,
    square_symmetric, square_tiled,
    square_tiled_worker, combine_tiled_partials
)


def get_machine_profile():
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
        except Exception:
            pass
    return profile


def generate_limbs(num_limbs: int, pattern: str, seed: int = 42) -> list[int]:
    """Generate limbs for testing."""
    random.seed(seed)
    MASK = (1 << 30) - 1
    
    if pattern == "dense-random":
        return [random.randint(0, MASK) for _ in range(num_limbs)]
    elif pattern == "max-carry":
        return [MASK] * num_limbs
    elif pattern == "sparse":
        limbs = [0] * num_limbs
        for i in range(0, num_limbs, max(1, num_limbs // 16)):
            limbs[i] = random.randint(1, MASK)
        return limbs
    else:
        raise ValueError(f"Unknown pattern: {pattern}")


def square_python_int(limbs: list[int]) -> int:
    """Reference: convert to Python int and square."""
    value = 0
    for i, limb in enumerate(limbs):
        value += limb << (30 * i)
    return value * value


def square_schoolbook(limbs: list[int]) -> list[int]:
    """Baseline schoolbook square (same as BinaryLimbBigInt.square)."""
    L = len(limbs)
    out = [0] * (2 * L)
    MASK = (1 << 30) - 1
    BITS = 30
    for i in range(L):
        carry = 0
        for j in range(L):
            prod = out[i + j] + limbs[i] * limbs[j] + carry
            out[i + j] = prod & MASK
            carry = prod >> BITS
        out[i + L] = carry
    return out


def normalize_limbs(limbs: list[int]) -> list[int]:
    """Normalize limbs (remove leading zeros)."""
    out = list(limbs)
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return out


def limbs_to_int(limbs: list[int]) -> int:
    """Convert limbs to Python int for comparison."""
    value = 0
    for i, limb in enumerate(limbs):
        value += limb << (30 * i)
    return value


def verify_square(limbs: list[int], result: list[int]) -> bool:
    """Verify square result against Python int."""
    expected = square_python_int(limbs)
    actual = limbs_to_int(result)
    return expected == actual


def run_schoolbook(limbs: list[int]) -> tuple[list[int], float]:
    """Run baseline schoolbook square."""
    start = time.perf_counter_ns()
    result = square_schoolbook(limbs)
    elapsed = time.perf_counter_ns() - start
    return normalize_limbs(result), elapsed / 1e9


def run_symmetric(limbs: list[int]) -> tuple[list[int], float]:
    """Run symmetric square."""
    MASK = (1 << 30) - 1
    BITS = 30
    start = time.perf_counter_ns()
    result = square_symmetric(limbs, MASK, BITS)
    elapsed = time.perf_counter_ns() - start
    return normalize_limbs(result), elapsed / 1e9


def run_tiled(limbs: list[int], tile_size: int) -> tuple[list[int], float]:
    """Run tiled square."""
    MASK = (1 << 30) - 1
    BITS = 30
    start = time.perf_counter_ns()
    result = square_tiled(limbs, tile_size, MASK, BITS)
    elapsed = time.perf_counter_ns() - start
    return normalize_limbs(result), elapsed / 1e9


def run_tiled_parallel(limbs: list[int], tile_size: int, workers: int) -> tuple[list[int], dict]:
    """Run tiled square in parallel."""
    MASK = (1 << 30) - 1
    BITS = 30
    L = len(limbs)
    num_tiles = (L + tile_size - 1) // tile_size
    
    # Generate tile coordinates (only tile_j >= tile_i for symmetry)
    tile_coords = []
    for ti in range(num_tiles):
        for tj in range(ti, num_tiles):
            tile_coords.append((ti, tj))
    
    # Distribute tiles among workers
    coords_per_worker = [[] for _ in range(workers)]
    for idx, coord in enumerate(tile_coords):
        coords_per_worker[idx % workers].append(coord)
    
    # Filter empty
    coords_per_worker = [c for c in coords_per_worker if c]
    
    start = time.perf_counter_ns()
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = []
        for coords in coords_per_worker:
            args = (limbs, coords, tile_size, MASK, BITS)
            futures.append(executor.submit(square_tiled_worker, args))
        
        partials_list = [f.result() for f in futures]
    
    result = combine_tiled_partials(partials_list, L, MASK, BITS)
    elapsed = time.perf_counter_ns() - start
    
    metrics = {
        "tiles": len(tile_coords),
        "workers": workers,
        "tile_size": tile_size,
    }
    
    return normalize_limbs(result), elapsed / 1e9, metrics


def _worker_wrapper_schoolbook(args):
    limbs, iters = args
    for _ in range(iters):
        square_schoolbook(limbs)


def _worker_wrapper_symmetric(args):
    limbs, iters = args
    MASK = (1 << 30) - 1
    BITS = 30
    for _ in range(iters):
        square_symmetric(limbs, MASK, BITS)


def _worker_wrapper_tiled(args):
    limbs, tile_size, iters = args
    MASK = (1 << 30) - 1
    BITS = 30
    for _ in range(iters):
        square_tiled(limbs, tile_size, MASK, BITS)


def _calibration_worker(q, fn, args):
    q.put(time.perf_counter_ns())
    q.put(fn(args))


def run_calibration(limbs: list[int], kernel: str, tile_size: int = None, workers: int = 1, 
                    iters: int = 4, timeout: float = 20.0) -> dict:
    """Calibrate kernel performance - run directly without multiprocessing for calibration."""
    try:
        if kernel == "schoolbook":
            fn = _worker_wrapper_schoolbook
            args = (limbs, iters)
        elif kernel == "symmetric":
            fn = _worker_wrapper_symmetric
            args = (limbs, iters)
        elif kernel == "tiled":
            fn = _worker_wrapper_tiled
            args = (limbs, tile_size, iters)
        elif kernel == "tiled-parallel":
            # Use single worker for calibration
            fn = _worker_wrapper_tiled
            args = (limbs, tile_size, iters)
        else:
            return {"status": "error", "error": f"Unknown kernel: {kernel}"}
        
        # Run directly in current process (calibration is fast)
        t0 = time.perf_counter_ns()
        fn(args)
        t1 = time.perf_counter_ns()
        
        median_iter_ns = (t1 - t0) / iters
        return {
            "status": "completed",
            "median_iter_ns": median_iter_ns,
            "total_ns": t1 - t0,
        }
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_verify():
    """Verify all kernels against Python int."""
    print("Verification:")
    
    patterns = ["dense-random", "max-carry", "sparse"]
    sizes = [1, 2, 4, 8, 16, 32, 64]
    
    for pattern in patterns:
        print(f"  Pattern: {pattern}")
        for size in sizes:
            limbs = generate_limbs(size, pattern)
            
            # Schoolbook
            res_sb, _ = run_schoolbook(limbs)
            ok_sb = verify_square(limbs, res_sb)
            
            # Symmetric
            res_sym, _ = run_symmetric(limbs)
            ok_sym = verify_square(limbs, res_sym)
            
            # Tiled
            for tile in [8, 16, 32]:
                res_tiled, _ = run_tiled(limbs, tile)
                ok_tiled = verify_square(limbs, res_tiled)
            
            if not (ok_sb and ok_sym and ok_tiled):
                print(f"    FAIL size={size} pattern={pattern}")
                return False
    
    print("  All verification tests passed.")
    return True


def _load_results(output):
    if output and os.path.exists(output):
        with open(output, "r") as f:
            return json.load(f)
    return {}

def _save_results(output, data):
    if output:
        with open(output, "w") as f:
            json.dump(data, f, indent=2)


def cmd_calibrate(args):
    print(f"Calibrating with {args.limbs} limbs, pattern={args.pattern}")
    limbs = generate_limbs(args.limbs, args.pattern, args.seed)
    
    kernels = ["schoolbook", "symmetric"]
    if args.tiles:
        for t in args.tiles:
            kernels.append(f"tiled-{t}")
    
    results = _load_results(args.output)
    results.setdefault("calibrate", [])
    
    for kernel in kernels:
        tile_size = None
        kernel_name = kernel
        if kernel.startswith("tiled-"):
            tile_size = int(kernel.split("-")[1])
            kernel_name = "tiled"
        
        print(f"  Engine: {kernel}")
        cal = run_calibration(limbs, kernel_name, 
                             tile_size=tile_size, workers=1, 
                             iters=args.max_cal_iters, timeout=args.calibration_timeout)
        print(f"    Status: {cal['status']}")
        if cal["status"] == "completed":
            print(f"    Median Iter: {cal['median_iter_ns']/1e6:.2f} ms")
            eta = cal['median_iter_ns'] * 1e-9
            print(f"    ETA (raw): {eta:.2f} s")
            print(f"    ETA (margin): {eta * 1.25:.2f} s")
        
        cal["kernel"] = kernel
        results["calibrate"].append(cal)
    
    _save_results(args.output, results)


def cmd_compare(args):
    print(f"Comparing with {args.limbs} limbs, pattern={args.pattern}")
    limbs = generate_limbs(args.limbs, args.pattern, args.seed)
    
    results = _load_results(args.output)
    results.setdefault("compare", [])
    
    # Reference: Python int
    start = time.perf_counter_ns()
    ref = square_python_int(limbs)
    t_py = time.perf_counter_ns() - start
    print(f"  Python int: {t_py/1e9:.6f} s")
    results["compare"].append({"kernel": "python-int", "time_s": t_py/1e9, "status": "completed"})
    
    # Schoolbook
    res_sb, t_sb = run_schoolbook(limbs)
    ok_sb = verify_square(limbs, res_sb)
    print(f"  Schoolbook: {t_sb:.6f} s {'OK' if ok_sb else 'FAIL'} speedup={t_py/t_sb:.2f}x")
    results["compare"].append({"kernel": "schoolbook", "time_s": t_sb, "status": "completed" if ok_sb else "failed"})
    
    # Symmetric
    res_sym, t_sym = run_symmetric(limbs)
    ok_sym = verify_square(limbs, res_sym)
    print(f"  Symmetric:  {t_sym:.6f} s {'OK' if ok_sym else 'FAIL'} speedup={t_py/t_sym:.2f}x")
    results["compare"].append({"kernel": "symmetric", "time_s": t_sym, "status": "completed" if ok_sym else "failed"})
    
    # Tiled variants
    for tile in args.tiles:
        res_tiled, t_tiled = run_tiled(limbs, tile)
        ok_tiled = verify_square(limbs, res_tiled)
        print(f"  Tiled-{tile}:   {t_tiled:.6f} s {'OK' if ok_tiled else 'FAIL'} speedup={t_py/t_tiled:.2f}x")
        results["compare"].append({"kernel": f"tiled-{tile}", "time_s": t_tiled, "status": "completed" if ok_tiled else "failed"})
    
    # Parallel tiled
    for tile in args.tiles:
        for workers in args.workers:
            res_par, t_par, metrics = run_tiled_parallel(limbs, tile, workers)
            ok_par = verify_square(limbs, res_par)
            eff = t_sb / (t_par * workers) if t_par > 0 else 0
            print(f"  Tiled-{tile}-P{workers}: {t_par:.6f} s {'OK' if ok_par else 'FAIL'} speedup={t_py/t_par:.2f}x eff={eff:.2f}")
            results["compare"].append({"kernel": f"tiled-{tile}-P{workers}", "time_s": t_par, "status": "completed" if ok_par else "failed", "efficiency": eff})
    
    _save_results(args.output, results)


def cmd_tune(args):
    print(f"Tuning with {args.limbs} limbs, pattern={args.pattern}")
    limbs = generate_limbs(args.limbs, args.pattern, args.seed)
    
    results = _load_results(args.output)
    
    # Handle both new and old tune format
    if "tune" not in results:
        results["tune"] = {"tiles": []}
    elif "tiles" not in results["tune"]:
        results["tune"]["tiles"] = []
    
    best_time = float('inf')
    best_tile = None
    
    for tile in args.tiles:
        # Sequential
        res, t_seq = run_tiled(limbs, tile)
        ok = verify_square(limbs, res)
        if ok and t_seq < best_time:
            best_time = t_seq
            best_tile = tile
        print(f"  Tile {tile} seq: {t_seq:.6f} s {'OK' if ok else 'FAIL'}")
        results["tune"]["tiles"].append({"tile": tile, "sequential_time_s": t_seq, "status": "completed" if ok else "failed"})
        
        # Parallel
        for workers in args.workers:
            res_par, t_par, metrics = run_tiled_parallel(limbs, tile, workers)
            ok_par = verify_square(limbs, res_par)
            eff = t_seq / (t_par * workers) if t_par > 0 else 0
            print(f"  Tile {tile} P{workers}: {t_par:.6f} s {'OK' if ok_par else 'FAIL'} eff={eff:.2f}")
            results["tune"]["tiles"].append({"tile": tile, "workers": workers, "time_s": t_par, "efficiency": eff, "status": "completed" if ok_par else "failed"})
    
    print(f"\nBest sequential tile: {best_tile} ({best_time:.6f} s)")
    
    results["tune"]["limbs"] = args.limbs
    results["tune"]["pattern"] = args.pattern
    results["tune"]["best_tile"] = best_tile
    results["tune"]["best_time"] = best_time
    
    _save_results(args.output, results)


def cmd_scale(args):
    print(f"Scaling: limbs={args.limbs}")
    results = _load_results(args.output)
    results.setdefault("scale", [])
    
    for limbs_n in args.limbs:
        print(f"\n  Limbs: {limbs_n}")
        limbs = generate_limbs(limbs_n, args.pattern, args.seed)
        
        # Use best tile from tune or default
        tile = args.tile or 32
        res, t = run_tiled(limbs, tile)
        ok = verify_square(limbs, res)
        print(f"    Tiled-{tile} seq: {t:.6f} s {'OK' if ok else 'FAIL'}")
        results["scale"].append({"limbs": limbs_n, "tile": tile, "workers": 1, "time_s": t, "status": "completed" if ok else "failed"})
        
        for workers in args.workers:
            res_par, t_par, _ = run_tiled_parallel(limbs, tile, workers)
            ok_par = verify_square(limbs, res_par)
            print(f"    Tiled-{tile} P{workers}: {t_par:.6f} s {'OK' if ok_par else 'FAIL'}")
            results["scale"].append({"limbs": limbs_n, "tile": tile, "workers": workers, "time_s": t_par, "status": "completed" if ok_par else "failed"})
    
    _save_results(args.output, results)


def cmd_report(args):
    if not os.path.exists(args.output):
        print("No data found.")
        return
    
    with open(args.output, "r") as f:
        data = json.load(f)
    
    profile = get_machine_profile()
    
    report_path = Path("docs/performance/tiled-bigint-0.37.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    md = [
        "# S3 0.37 Tiled BigInt Square Performance Lab",
        "",
        "## Hardware Profile",
        f"- **OS**: {profile['os']}",
        f"- **CPU**: {profile['cpu_name']}",
        f"- **Logical CPUs**: {profile['logical_cpus']}",
        f"- **Physical Cores**: {profile['physical_cpus']}",
        "",
    ]
    
    # Compare results
    if "compare" in data and data["compare"]:
        md.extend(["## Kernel Comparison (1024 limbs, dense-random)", "", "| Kernel | Time (s) | Speedup vs Python | Status |", "|---|---|---|---|"])
        py_time = None
        for c in data["compare"]:
            if c.get("kernel") == "python-int":
                py_time = c.get("time_s", 0)
                break
        
        for c in data["compare"]:
            speedup = f"{py_time / c.get('time_s', 1):.2f}x" if py_time and c.get('time_s', 0) > 0 else "-"
            md.append(f"| {c['kernel']} | {c.get('time_s', 0):.6f} | {speedup} | {c.get('status', '-')} |")
    
    # Tune results
    if "tune" in data and "tiles" in data["tune"]:
        md.extend(["", "## Tile Tuning (1024 limbs, dense-random)", "", "| Tile | Workers | Time (s) | Efficiency | Status |", "|---|---|---|---|---|"])
        for t in data["tune"]["tiles"]:
            if "workers" in t:
                md.append(f"| {t['tile']} | {t['workers']} | {t.get('time_s', 0):.6f} | {t.get('efficiency', 0):.2f} | {t.get('status', '-')} |")
            else:
                md.append(f"| {t['tile']} | 1 | {t.get('sequential_time_s', 0):.6f} | - | {t.get('status', '-')} |")
        
        md.extend(["", f"**Best sequential tile**: {data['tune'].get('best_tile', 'N/A')} ({data['tune'].get('best_time', 0):.6f} s)"])
    
    # Scale results
    if "scale" in data and data["scale"]:
        md.extend(["", "## Scaling Analysis", "", "| Limbs | Tile | Workers | Time (s) | Status |", "|---|---|---|---|---|"])
        for s in data["scale"]:
            md.append(f"| {s['limbs']} | {s['tile']} | {s['workers']} | {s.get('time_s', 0):.6f} | {s.get('status', '-')} |")
        
        # Compute empirical alpha
        md.extend(["", "### Empirical Scaling (Sequential)", "| Size | Time (s) | Alpha |", "|---|---|---|"])
        seq_times = {}
        for s in data["scale"]:
            if s["workers"] == 1:
                seq_times[s["limbs"]] = s.get("time_s", 0)
        
        sizes = sorted(seq_times.keys())
        for i in range(1, len(sizes)):
            L1, L2 = sizes[i-1], sizes[i]
            T1, T2 = seq_times[L1], seq_times[L2]
            if T1 > 0:
                alpha = math.log(T2 / T1) / math.log(L2 / L1)
                md.append(f"| {L1}->{L2} | {T1:.6f}->{T2:.6f} | {alpha:.2f} |")
    
    # Calibration results
    if "calibrate" in data:
        md.extend(["", "### Calibration (1024 limbs)", "| Kernel | Status | Median Iter (ms) |", "|---|---|---|"])
        for c in data["calibrate"]:
            mi = f"{c.get('median_iter_ns', 0)/1e6:.2f}" if c.get('status') == 'completed' else '-'
            md.append(f"| {c['kernel']} | {c['status']} | {mi} |")
    
    md.extend(["", "## Conclusion", "Tiled bigint square evaluation complete."])
    
    with open(report_path, "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"Report written to {report_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["verify", "calibrate", "compare", "tune", "scale", "report"])
    parser.add_argument("--limbs", type=int, default=1024)
    parser.add_argument("--limbs-list", type=str, default="512,1024,2048,4096")
    parser.add_argument("--pattern", type=str, default="dense-random", choices=["dense-random", "max-carry", "sparse"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tiles", type=str, default="8,16,32,64,128,256")
    parser.add_argument("--tile", type=int, default=None)
    parser.add_argument("--workers", type=str, default="1,2,4")
    parser.add_argument("--max-cal-iters", type=int, default=4)
    parser.add_argument("--calibration-timeout", type=int, default=20)
    parser.add_argument("--hard-timeout", type=int, default=180)
    parser.add_argument("--eta-limit", type=int, default=120)
    parser.add_argument("--output", type=str, default=".tmp-tiled-bigint-0.37-results.json")
    
    args = parser.parse_args()
    
    if args.command == "verify":
        run_verify()
    elif args.command == "calibrate":
        args.tiles = [int(x) for x in args.tiles.split(",")] if args.tiles else []
        cmd_calibrate(args)
    elif args.command == "compare":
        args.tiles = [int(x) for x in args.tiles.split(",")] if args.tiles else []
        args.workers = [int(x) for x in args.workers.split(",")] if args.workers else []
        cmd_compare(args)
    elif args.command == "tune":
        args.tiles = [int(x) for x in args.tiles.split(",")] if args.tiles else []
        args.workers = [int(x) for x in args.workers.split(",")] if args.workers else []
        cmd_tune(args)
    elif args.command == "scale":
        args.limbs = [int(x) for x in args.limbs_list.split(",")]
        args.workers = [int(x) for x in args.workers.split(",")] if args.workers else []
        cmd_scale(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()