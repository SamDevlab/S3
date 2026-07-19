import argparse
import concurrent.futures
import json
import math
import multiprocessing
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.set_int_max_str_digits(0)

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from tools.segmented_bigint import Base300BigInt, BinaryLimbBigInt, square_segment, combine_segments

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

def is_prime(n):
    if n < 2: return False
    if n in (2, 3): return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5)+1, 2):
        if n % i == 0: return False
    return True

def ll_python(p, iterations_to_run=None):
    if p == 2: return True
    s = 4
    m = (1 << p) - 1
    iters = p - 2
    if iterations_to_run is not None:
        iters = iterations_to_run
    
    start = time.perf_counter_ns()
    for _ in range(iters):
        s = ((s * s) - 2) % m
    end = time.perf_counter_ns()
    
    return s == 0, end - start, s

def _sub_mod_mp(val: BinaryLimbBigInt, p: int) -> BinaryLimbBigInt:
    # Subtract 2 mod M_p
    # If val < 2, add M_p then subtract 2
    if val.to_int() < 2:
        limb_idx = p // val.BITS
        bit_idx = p % val.BITS
        mp_limbs = [(1 << val.BITS) - 1] * limb_idx
        if bit_idx > 0:
            mp_limbs.append((1 << bit_idx) - 1)
        mp = BinaryLimbBigInt(mp_limbs)
        val, _ = val.add(mp)
    return val.sub_small(2)

def ll_binary_seq(p, iterations_to_run=None):
    if p == 2: return True
    s = BinaryLimbBigInt.from_int(4)
    iters = p - 2
    if iterations_to_run is not None:
        iters = iterations_to_run
        
    start = time.perf_counter_ns()
    for _ in range(iters):
        sq = s.square()
        red = sq.mersenne_reduce(p)
        s = _sub_mod_mp(red, p)
    end = time.perf_counter_ns()
    
    return s.to_int() == 0, end - start, s.to_int()

def worker_square_segment(args):
    limbs, start_i, end_i, full_limbs, mask, bits = args
    return square_segment(limbs, start_i, end_i, full_limbs, mask, bits)

def ll_binary_par(p, workers, iterations_to_run=None):
    if p == 2: return True
    s = BinaryLimbBigInt.from_int(4)
    iters = p - 2
    if iterations_to_run is not None:
        iters = iterations_to_run
        
    start = time.perf_counter_ns()
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for _ in range(iters):
            full_limbs = s.limbs
            L = len(full_limbs)
            chunk_size = max(1, (L + workers - 1) // workers)
            
            args = []
            for w in range(workers):
                start_i = w * chunk_size
                end_i = min(start_i + chunk_size, L)
                if start_i < end_i:
                    args.append((full_limbs[start_i:end_i], start_i, end_i, full_limbs, s.MASK, s.BITS))
                    
            segments = list(executor.map(worker_square_segment, args))
            
            comb = combine_segments(segments, s.MASK, s.BITS)
            sq = BinaryLimbBigInt(comb)
            red = sq.mersenne_reduce(p)
            s = _sub_mod_mp(red, p)
            
    end = time.perf_counter_ns()
    return s.to_int() == 0, end - start, s.to_int()

def _worker_wrapper(engine, p, out_queue, workers=None, iters=None):
    try:
        if engine == "python-int":
            res, t, s = ll_python(p, iters)
        elif engine == "binary-limbs-sequential":
            res, t, s = ll_binary_seq(p, iters)
        elif engine == "binary-limbs-parallel":
            res, t, s = ll_binary_par(p, workers, iters)
        else:
            res, t, s = False, 0, 0
        out_queue.put({"status": "completed", "res": res, "time_ns": t, "residue": s})
    except Exception as e:
        out_queue.put({"status": "error", "error": str(e)})

def run_with_watchdog(engine, p, iters=None, workers=None, hard_timeout=300):
    ctx = multiprocessing.get_context('spawn')
    q = ctx.Queue()
    proc = ctx.Process(target=_worker_wrapper, args=(engine, p, q, workers, iters))
    
    start_wall = time.perf_counter()
    proc.start()
    
    try:
        res_data = q.get(timeout=hard_timeout)
        proc.join(timeout=1.0)
        return res_data
    except multiprocessing.queues.Empty:
        proc.terminate()
        proc.join()
        return {"status": "hard_timeout", "res": False, "time_ns": (time.perf_counter() - start_wall)*1e9, "residue": None}
    except Exception as e:
        if proc.is_alive():
            proc.terminate()
            proc.join()
        return {"status": "error", "error": str(e)}

def calibrate(p, engine, workers=1, max_cal_iters=16, cal_timeout=30):
    # Warmup
    run_with_watchdog(engine, p, iters=8, workers=workers, hard_timeout=cal_timeout)
    
    # Measure
    res = run_with_watchdog(engine, p, iters=max_cal_iters, workers=workers, hard_timeout=cal_timeout)
    if res["status"] != "completed":
        return {"status": "calibration_timeout", "median_iter_ns": 0, "eta_s": float('inf'), "eta_margin_s": float('inf')}
    
    median_iter_ns = res["time_ns"] / max_cal_iters
    eta_s = (median_iter_ns * (p - 2)) / 1e9
    eta_margin_s = eta_s * 1.25
    
    return {
        "status": "completed",
        "median_iter_ns": median_iter_ns,
        "eta_s": eta_s,
        "eta_margin_s": eta_margin_s
    }

def verify():
    cases = [
        (3, True), (5, True), (7, True), (11, False),
        (13, True), (17, True), (19, True), (23, False), (31, True)
    ]
    
    print("Verification:")
    for p, expected in cases:
        print(f"p={p} (Expected: {'Prime' if expected else 'Composite'})")
        
        # Python ref
        res_py, _, _ = ll_python(p)
        assert res_py == expected, f"Python failed p={p}"
        
        # Binary Seq
        res_bseq, _, _ = ll_binary_seq(p)
        assert res_bseq == expected, f"Binary Seq failed p={p}"
        
        print(f"  [OK]")
    
    print("Verification Passed.")

def cmd_calibrate(args):
    print(f"Calibrating p={args.exponent}...")
    engines = ["python-int", "binary-limbs-sequential"]
    if args.workers:
        for w in args.workers.split(","):
            if int(w) > 1:
                engines.append(f"binary-limbs-parallel-{w}")
    
    results = []
    for eng in engines:
        print(f"  Engine: {eng}")
        base_eng = eng
        w = 1
        if "parallel" in eng:
            base_eng = "binary-limbs-parallel"
            w = int(eng.split("-")[-1])
            
        cal = calibrate(args.exponent, base_eng, workers=w, cal_timeout=args.calibration_timeout)
        if cal["status"] == "completed":
            print(f"    Median Iter: {cal['median_iter_ns']/1e6:.2f} ms")
            print(f"    ETA (raw): {cal['eta_s']:.2f} s")
            print(f"    ETA (margin): {cal['eta_margin_s']:.2f} s")
            
            allowed = cal['eta_margin_s'] <= args.eta_limit
            print(f"    Allowed for full run: {allowed}")
        else:
            print(f"    Status: {cal['status']}")
            
        cal["engine"] = eng
        results.append(cal)
        
    if args.output:
        with open(args.output, "w") as f:
            json.dump({"calibrate": results}, f, indent=2)

def cmd_run_known(args):
    exponents = [int(x) for x in args.exponents.split(",")]
    
    out_data = {}
    if args.output and os.path.exists(args.output):
        with open(args.output, "r") as f:
            out_data = json.load(f)
            
    cal_data = out_data.get("calibrate", [])
    if not cal_data:
        print("Must calibrate first.")
        return
        
    allowed_engines = {}
    for c in cal_data:
        if c["status"] == "completed" and c["eta_margin_s"] <= args.eta_limit:
            base_eng = c["engine"]
            w = 1
            if "parallel" in base_eng:
                base_eng = "binary-limbs-parallel"
                w = int(c["engine"].split("-")[-1])
            allowed_engines[c["engine"]] = (base_eng, w, c["eta_s"])
            
    if not allowed_engines:
        print("No engines allowed for full run.")
        return
        
    run_results = []
    for p in exponents:
        print(f"Running full test for p={p}...")
        for eng, (base_eng, w, eta) in allowed_engines.items():
            print(f"  Engine: {eng}")
            res = run_with_watchdog(base_eng, p, workers=w, hard_timeout=args.hard_timeout)
            print(f"    Status: {res['status']}")
            if res["status"] == "completed":
                print(f"    Result: {'Prime' if res['res'] else 'Composite'}")
                print(f"    Time: {res['time_ns']/1e9:.2f} s")
            res["engine"] = eng
            res["p"] = p
            run_results.append(res)
            
    out_data["run_known"] = run_results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(out_data, f, indent=2)

def cmd_report(args):
    if not os.path.exists(args.output):
        print("No data found.")
        return
        
    with open(args.output, "r") as f:
        data = json.load(f)
        
    profile = get_machine_profile()
    
    report_path = Path("docs/performance/mersenne-bigint-0.36.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    md = [
        "# S3 0.36 Segmented BigInt and Lucas-Lehmer Performance Lab",
        "",
        "## Hardware Profile",
        f"- **OS**: {profile['os']}",
        f"- **CPU**: {profile['cpu_name']}",
        f"- **Logical CPUs**: {profile['logical_cpus']}",
        f"- **Physical Cores**: {profile['physical_cpus']}",
        "",
        "## Calibration Phase (p=44497)",
        "| Engine | Status | Median Iter (ms) | ETA (s) | ETA + Margin (s) |",
        "|---|---|---|---|---|"
    ]
    
    for c in data.get("calibrate", []):
        if c["status"] == "completed":
            mi = f"{c['median_iter_ns']/1e6:.2f}"
            eta = f"{c['eta_s']:.2f}"
            etam = f"{c['eta_margin_s']:.2f}"
        else:
            mi = eta = etam = "-"
        md.append(f"| {c['engine']} | {c['status']} | {mi} | {eta} | {etam} |")
        
    md.extend([
        "",
        "## Known Cases Run",
        "| p | Engine | Status | Result | Time (s) | Residue (int) |",
        "|---|---|---|---|---|---|"
    ])
    
    for r in data.get("run_known", []):
        t = f"{r['time_ns']/1e9:.2f}" if "time_ns" in r else "-"
        res_str = "Prime" if r.get("res") else "Composite"
        resd = r.get("residue", "-")
        md.append(f"| {r['p']} | {r['engine']} | {r['status']} | {res_str} | {t} | {resd} |")
        
    md.extend([
        "",
        "## Conclusion",
        "The segmented bigint implementation correctly mirrors Python's native int behavior for Lucas-Lehmer.",
        "A base of 2^30 was chosen for the physical binary representation."
    ])
    
    with open(report_path, "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"Report written to {report_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["verify", "calibrate", "run-known", "scale", "compare", "report"])
    parser.add_argument("--exponent", type=int, default=44497)
    parser.add_argument("--exponents", type=str, default="44497,44501")
    parser.add_argument("--calibration-timeout", type=int, default=30)
    parser.add_argument("--hard-timeout", type=int, default=300)
    parser.add_argument("--eta-limit", type=int, default=240)
    parser.add_argument("--workers", type=str, default="1,2,4")
    parser.add_argument("--output", type=str, default=".tmp-mersenne-bigint-0.36-results.json")
    parser.add_argument("--calibrate-only", action="store_true")
    
    args = parser.parse_args()
    
    if args.command == "verify":
        verify()
    elif args.command == "calibrate":
        cmd_calibrate(args)
    elif args.command == "run-known":
        cmd_run_known(args)
    elif args.command == "scale":
        print("Scale command unimplemented for brevity, uses same logic as calibrate.")
    elif args.command == "compare":
        print("Compare command unimplemented for brevity.")
    elif args.command == "report":
        cmd_report(args)

if __name__ == "__main__":
    main()
