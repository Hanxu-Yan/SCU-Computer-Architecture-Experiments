"""Check saved results, source/trace integrity, and a standalone CLI replay."""
from collections import defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def audit():
    raw = list(csv.DictReader((ROOT / "results/raw_runs.csv").open(encoding="utf-8-sig")))
    summary = list(csv.DictReader((ROOT / "results/summary.csv").open(encoding="utf-8-sig")))
    manifest = json.loads((ROOT / "traces/manifest.json").read_text())
    meta = json.loads((ROOT / "results/run_metadata.json").read_text())
    params = json.loads((ROOT / "results/parameters.json").read_text())
    assert len(raw) == meta["runs"] == params["total_runs"] == 768
    assert len(summary) == meta["summary_rows"] == 300
    assert sum(int(r["accesses"]) + int(r["warmup_probes"]) for r in raw) == meta["simulated_line_probes"]
    for w in manifest["workloads"]:
        assert hashlib.sha256((ROOT / "traces" / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        if w["source"] == "instrumented_C":
            assert w["kernel_validation"]["validated"] is True
    for name, digest in meta["source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f"Source changed: {name}"
    keys = ["experiment", "workload", "capacity_bytes", "block_bytes", "ways", "policy", "warmup_probes"]
    groups = defaultdict(list)
    for r in raw:
        hits, misses, n = (int(r[k]) for k in ["hits", "misses", "accesses"])
        assert hits + misses == n
        assert int(r["reads"]) + int(r["writes"]) == n
        assert int(r["read_misses"]) + int(r["write_misses"]) == misses
        assert int(r["writebacks"]) <= int(r["evictions"]) <= misses
        assert math.isclose(float(r["hit_rate"]), hits/n, abs_tol=1e-14)
        assert int(r["capacity_bytes"]) == int(r["block_bytes"]) * int(r["ways"]) * int(r["sets"])
        assert int(r["input_references"]) == n + int(r["warmup_probes"])
        if r["policy"] == "LRU":
            assert sum(int(r[k]) for k in ["compulsory", "capacity", "conflict"]) == misses
        else:
            assert all(r[k] == "" for k in ["compulsory", "capacity", "conflict"])
        groups[tuple(r[k] for k in keys)].append(r)
    assert len(groups) == len(summary)
    for s in summary:
        group = groups[tuple(s[k] for k in keys)]
        values = [int(g["hits"]) / int(g["accesses"]) * 100 for g in group]
        assert len(group) == int(s["runs"])
        if s["policy"] == "Random" and int(s["ways"]) > 1:
            assert sorted(int(g["seed"]) for g in group) == list(range(10))
        else:
            assert len(group) == 1
        mean = sum(values) / len(values)
        sd = statistics.stdev(values) if len(values) > 1 else 0
        half = 2.2621571628540993 * sd / math.sqrt(len(values))
        assert math.isclose(mean, float(s["hit_rate_pct"]), abs_tol=1e-10)
        assert math.isclose(half, float(s["ci95_half_pp"]), abs_tol=1e-10)
    for w in manifest["workloads"]:
        dm = [r for r in raw if r["experiment"] == "main" and r["workload"] == w["name"] and r["ways"] == "1"]
        assert len({r["hits"] for r in dm}) == 1
    for r in raw:
        if r["experiment"] == "main" and r["workload"] in ("sequential", "row_scan"):
            assert float(r["hit_rate"]) == .9375
    replay = subprocess.run([sys.executable, str(ROOT / "cache_sim.py"),
                             str(ROOT / "traces/hot_cold.trace.gz"), "--classify"],
                            check=True, capture_output=True, text=True)
    actual = json.loads(replay.stdout)
    expected = next(r for r in raw if r["experiment"] == "main" and r["workload"] == "hot_cold"
                    and r["ways"] == "4" and r["policy"] == "LRU")
    for key in ["hits", "misses", "writebacks", "compulsory", "capacity", "conflict"]:
        assert actual[key] == int(expected[key])
    result = dict(passed=True, audited_utc=datetime.now(timezone.utc).isoformat(),
                  raw_runs=len(raw), summary_groups=len(summary), trace_checksums=12,
                  source_checksums=len(meta["source_sha256"]), c_kernel_validations=4,
                  cli_replay="hot_cold / 4096 B / 64 B / 4-way / LRU: identical",
                  checks=["counter conservation", "configuration accounting", "3C accounting",
                          "replacement seeds", "summary mean and CI", "source and trace hashes",
                          "direct-mapped policy equivalence", "sequential analytical rate", "CLI replay"])
    (ROOT / "results/audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    audit()
