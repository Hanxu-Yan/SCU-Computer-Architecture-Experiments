"""Generate controlled traces and run C kernels with explicit array tracing."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import random
import subprocess
from cache_sim import read_trace

ROOT = Path(__file__).resolve().parent
TRACE_SEED = 20261107


def write_trace(path, refs):
    # Stable gzip header: checksum reproducible across run dates.
    with open(path, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as g:
            with io.TextIOWrapper(g, encoding="utf-8", newline="\n") as f:
                for op, address, size in refs:
                    f.write(f"{op} 0x{address:x} {size}\n")


def synthetic():
    yield "sequential", "顺序扫描", "synthetic", "64 KiB 数组，4 B 步长，重复 4 轮", [
        ("R", a, 4) for _ in range(4) for a in range(0, 65536, 4)]
    yield "small_reuse", "小工作集复用", "synthetic", "2 KiB 数组，4 B 步长，重复 64 轮", [
        ("R", a, 4) for _ in range(64) for a in range(0, 2048, 4)]
    for k, rounds in [(2, 16384), (8, 4096), (5, 8192)]:
        name = f"conflict_{k}" if k != 5 else "cycle_5"
        label = f"{k} 块同组循环"
        yield name, label, "synthetic", f"{k} 个地址间隔 4096 B，循环 {rounds} 轮", [
            ("R", i * 4096, 4) for _ in range(rounds) for i in range(k)]
    yield "capacity_cycle", "65 块循环", "synthetic", "连续 65 个 64 B 块，各读 4 B，循环 512 轮", [
        ("R", i * 64, 4) for _ in range(512) for i in range(65)]
    rng = random.Random(TRACE_SEED)
    hot = []
    for _ in range(100000):
        block = rng.randrange(48) if rng.random() < 0.9 else rng.randrange(48, 1024)
        address = block * 64 + rng.randrange(16) * 4
        hot.append(("W" if rng.random() < 0.2 else "R", address, 4))
    yield "hot_cold", "热点混合", "synthetic", "90% 概率访问 48 个热点块，其余访问 976 个冷块；20% 写", hot
    rng = random.Random(TRACE_SEED + 1)
    yield "uniform_random", "均匀随机", "synthetic", "1024 个块内均匀选择 4 B 字，100000 次只读访问", [
        ("R", rng.randrange(16384) * 4, 4) for _ in range(100000)]


def generate():
    out = ROOT / "traces"
    out.mkdir(exist_ok=True)
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    subprocess.run(["cc", "-O2", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(ROOT / "kernels.c"), "-o", str(build / "kernels")], check=True)
    records = []
    for name, label, source, desc, refs in synthetic():
        path = out / f"{name}.trace.gz"
        write_trace(path, refs)
        records.append(dict(name=name, label=label, source=source, description=desc))
    names = [("row_scan", "按行遍历"), ("column_scan", "按列遍历"),
             ("transpose_naive", "朴素矩阵转置"), ("transpose_tiled", "8×8 分块转置")]
    for name, label in names:
        path = build / f"{name}.trace"
        result = subprocess.run([str(build / "kernels"), name, str(path)],
                                check=True, text=True, capture_output=True)
        validation = json.loads(result.stdout)
        write_trace(out / f"{name}.trace.gz", read_trace(path))
        path.unlink()
        records.append(dict(name=name, label=label, source="instrumented_C",
                            description="128×128 uint32 矩阵，4 轮；仅记录显式数组读写；固定逻辑基址",
                            kernel_validation=validation))
    for r in records:
        path = out / f"{r['name']}.trace.gz"
        refs = list(read_trace(path))
        r.update(file=path.name, references=len(refs),
                 reads=sum(op == "R" for op, _, _ in refs),
                 writes=sum(op == "W" for op, _, _ in refs),
                 unique_64B_blocks=len({a // 64 for _, a, _ in refs}),
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    manifest = dict(trace_seed=TRACE_SEED, trace_format="R|W byte_address byte_size",
                    c_address_model={"A": "0x100000", "B": "0x200000"},
                    excluded="初始化、校验、循环变量、栈、指令取址、编译器额外访存",
                    workloads=records)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Generated {len(records)} traces, {sum(r['references'] for r in records):,} references.")
    return manifest


if __name__ == "__main__":
    generate()
