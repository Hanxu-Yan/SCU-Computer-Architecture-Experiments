"""Run the declared experiment matrix; keep every seed's raw measurements."""
import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from cache_sim import Config, expand_trace, read_trace, simulate
from generate_traces import generate

ROOT = Path(__file__).resolve().parent
SEEDS = list(range(10))


def plan(workloads):
    jobs = []
    for w in workloads:
        name = w["name"]
        # Main factorial design. Direct mapped Random has no victim choice.
        for ways in [1, 2, 4, 8, 64]:
            for policy in ["LRU", "FIFO", "Random"]:
                seeds = SEEDS if policy == "Random" and ways > 1 else [0]
                for seed in seeds:
                    jobs.append(("main", name, Config(4096, 64, ways, policy, seed), 0))
        for capacity in [1024, 2048, 4096, 8192, 16384]:
            jobs.append(("capacity", name, Config(capacity, 64, 4), 0))
        for block in [16, 32, 64, 128]:
            jobs.append(("block_size", name, Config(4096, block, 4), 0))
        if name in ["hot_cold", "uniform_random", "cycle_5", "transpose_tiled"]:
            for policy in ["LRU", "FIFO", "Random"]:
                for seed in SEEDS if policy == "Random" else [0]:
                    jobs.append(("warmup", name, Config(4096, 64, 4, policy, seed), 4096))
    return jobs


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def aggregate(rows):
    keys = ["experiment", "workload", "capacity_bytes", "block_bytes",
            "ways", "policy", "warmup_probes"]
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    summary = []
    for key, group in groups.items():
        out = dict(zip(keys, key))
        values = [g["hit_rate"] * 100 for g in group]
        n = len(values)
        mean = statistics.mean(values)
        std = statistics.stdev(values) if n > 1 else 0
        # Exact fixed experiment: n=10 Random seeds, t_(.975,9).
        half = 2.2621571628540993 * std / n ** 0.5 if n > 1 else 0
        out.update(runs=n, accesses=group[0]["accesses"], hit_rate_pct=mean,
                   sd_pp=std, ci95_half_pp=half, ci95_low_pct=mean-half,
                   ci95_high_pct=mean+half, min_hit_rate_pct=min(values),
                   max_hit_rate_pct=max(values))
        for field in ["hits", "misses", "writebacks", "memory_read_bytes",
                      "writeback_bytes", "compulsory", "capacity", "conflict"]:
            out[field + "_mean"] = (statistics.mean(g[field] for g in group)
                                    if group[0][field] is not None else None)
        summary.append(out)
    return summary


def run(regenerate=False):
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    manifest_path = ROOT / "traces/manifest.json"
    manifest = generate() if regenerate or not manifest_path.exists() else json.loads(manifest_path.read_text())
    jobs = plan(manifest["workloads"])
    params = {
        "main": {"capacity_bytes": 4096, "block_bytes": 64, "ways": [1, 2, 4, 8, 64],
                 "policies": ["LRU", "FIFO", "Random"]},
        "random_seeds": SEEDS,
        "capacity_sweep_bytes": [1024, 2048, 4096, 8192, 16384],
        "block_sweep_bytes": [16, 32, 64, 128],
        "warmup_probes": 4096, "write_policy": "write-back, write-allocate",
        "prefetch": False, "final_flush": False,
        "ci": "Student t, df=9, two-sided 95%, across replacement seeds on one fixed trace",
        "total_runs": len(jobs),
    }
    (results / "parameters.json").write_text(json.dumps(params, indent=2) + "\n")
    started = time.perf_counter()
    traces, expanded = {}, {}
    for w in manifest["workloads"]:
        p = ROOT / "traces" / w["file"]
        if hashlib.sha256(p.read_bytes()).hexdigest() != w["sha256"]:
            raise ValueError(f"Trace checksum mismatch: {p}")
        traces[w["name"]] = list(read_trace(p))
    rows = []
    rawpath = results / "raw_runs.csv"
    with open(rawpath, "w", encoding="utf-8-sig", newline="") as output:
        writer = None
        for i, (experiment, name, config, warmup) in enumerate(jobs, 1):
            key = (name, config.block_size)
            if key not in expanded:
                expanded[key] = expand_trace(traces[name], config.block_size)
            probes = expanded[key]
            result = simulate(probes, config, warmup, classify=config.policy == "LRU")
            assert result["accesses"] == len(probes) - warmup
            assert result["hits"] + result["misses"] == result["accesses"]
            assert result["read_misses"] + result["write_misses"] == result["misses"]
            if config.policy == "LRU":
                assert sum(result[k] for k in ("compulsory", "capacity", "conflict")) == result["misses"]
            row = dict(experiment=experiment, workload=name, capacity_bytes=config.capacity,
                       block_bytes=config.block_size, ways=config.ways, sets=config.sets,
                       policy=config.policy, seed=config.seed if config.policy == "Random" else "",
                       warmup_probes=warmup, input_references=len(traces[name]), **result)
            if writer is None:
                writer = csv.DictWriter(output, fieldnames=list(row))
                writer.writeheader()
            writer.writerow(row)
            rows.append(row)
            if i % 50 == 0 or i == len(jobs):
                output.flush()
                print(f"{i}/{len(jobs)} runs; {time.perf_counter()-started:.1f}s", flush=True)
    summary = aggregate(rows)
    write_csv(results / "summary.csv", summary)
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in ROOT.glob("*") if p.suffix in [".py", ".c"]}
    metadata = dict(completed_utc=datetime.now(timezone.utc).isoformat(),
                    python=sys.version, platform=platform.platform(),
                    compiler=subprocess.run(["cc", "--version"], capture_output=True, text=True).stdout,
                    elapsed_simulator_seconds=time.perf_counter()-started,
                    runs=len(rows), summary_rows=len(summary),
                    simulated_line_probes=sum(r["accesses"] + r["warmup_probes"] for r in rows),
                    source_sha256=source_hashes,
                    note="elapsed_simulator_seconds is host runtime, not simulated CPU time")
    (results / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: metadata[k] for k in ["runs", "summary_rows", "simulated_line_probes",
                                              "elapsed_simulator_seconds"]}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--regenerate", action="store_true")
    run(p.parse_args().regenerate)
