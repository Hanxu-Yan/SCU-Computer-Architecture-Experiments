"""Single-level, trace-driven data cache. Python standard library only.

Trace format: R|W byte_address byte_size, one access per line.
Address may be decimal or 0x-prefixed hex. # starts a comment.
Write-back, write-allocate; demand fetch; no prefetch or final flush.
Statistics count cache-line probes (a split access probes multiple lines).
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass, asdict
import gzip
import json
from pathlib import Path
import random
from typing import Iterable


@dataclass(frozen=True)
class Config:
    capacity: int = 4096
    block_size: int = 64
    ways: int = 4
    policy: str = "LRU"
    seed: int = 0

    def __post_init__(self):
        for name in ("capacity", "block_size", "ways"):
            value = getattr(self, name)
            if not isinstance(value, int) or value <= 0 or value & (value - 1):
                raise ValueError(f"{name} must be a positive power of two")
        if self.capacity < self.block_size * self.ways:
            raise ValueError("capacity must be >= block_size * ways")
        if self.policy not in ("LRU", "FIFO", "Random"):
            raise ValueError("policy must be LRU, FIFO or Random")

    @property
    def lines(self):
        return self.capacity // self.block_size

    @property
    def sets(self):
        return self.lines // self.ways


@dataclass
class Stats:
    accesses: int = 0
    hits: int = 0
    misses: int = 0
    reads: int = 0
    writes: int = 0
    read_misses: int = 0
    write_misses: int = 0
    evictions: int = 0
    writebacks: int = 0
    compulsory: int = 0
    capacity: int = 0
    conflict: int = 0


class Cache:
    def __init__(self, config: Config, classify: bool = False):
        if classify and config.policy != "LRU":
            raise ValueError("3C classification is restricted to LRU experiments")
        self.config = config
        # OrderedDict order is LRU->MRU for LRU, oldest->newest for FIFO.
        self.lines = [OrderedDict() for _ in range(config.sets)]
        # Random uses stable physical slots; replacing a line reuses its slot.
        self.slots = [[] for _ in range(config.sets)]
        self.rng = random.Random(config.seed)
        self.stats = Stats()
        self.classify = classify
        self.seen: set[int] = set()
        self.shadow: OrderedDict[int, None] = OrderedDict()

    def reset_stats(self):
        """Preserve cache, RNG, seen blocks, and FA-LRU shadow after warmup."""
        self.stats = Stats()

    def probe(self, block: int, write: bool = False) -> bool:
        if block < 0:
            raise ValueError("negative block")
        c, s = self.config, self.stats
        index = block % c.sets
        lines = self.lines[index]
        hit = block in lines
        s.accesses += 1
        s.writes += int(write)
        s.reads += int(not write)
        if hit:
            s.hits += 1
            if write:
                lines[block] = True
            if c.policy == "LRU":
                lines.move_to_end(block)
        else:
            s.misses += 1
            s.write_misses += int(write)
            s.read_misses += int(not write)
            if self.classify:
                if block not in self.seen:
                    s.compulsory += 1
                elif block not in self.shadow:
                    s.capacity += 1
                else:
                    s.conflict += 1
            if len(lines) == c.ways:
                if c.policy == "Random":
                    slot = self.rng.randrange(c.ways)
                    victim = self.slots[index][slot]
                    dirty = lines.pop(victim)
                    self.slots[index][slot] = block
                else:
                    _, dirty = lines.popitem(last=False)
                s.evictions += 1
                s.writebacks += int(dirty)
            elif c.policy == "Random":
                self.slots[index].append(block)
            lines[block] = write

        if self.classify:
            self.seen.add(block)
            if block in self.shadow:
                self.shadow.move_to_end(block)
            else:
                if len(self.shadow) == c.lines:
                    self.shadow.popitem(last=False)
                self.shadow[block] = None
        return hit

    def access(self, op: str, address: int, size: int = 4) -> list[bool]:
        if op not in ("R", "W") or address < 0 or size <= 0:
            raise ValueError("invalid memory reference")
        b = self.config.block_size
        return [self.probe(block, op == "W")
                for block in range(address // b, (address + size - 1) // b + 1)]

    def result(self):
        d = asdict(self.stats)
        d["hit_rate"] = d["hits"] / d["accesses"] if d["accesses"] else 0.0
        d["miss_rate"] = d["misses"] / d["accesses"] if d["accesses"] else 0.0
        d["memory_read_bytes"] = d["misses"] * self.config.block_size
        d["writeback_bytes"] = d["writebacks"] * self.config.block_size
        d["resident_dirty_lines"] = sum(sum(v.values()) for v in self.lines)
        if not self.classify:
            for key in ("compulsory", "capacity", "conflict"):
                d[key] = None
        return d


def read_trace(path: str | Path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            fields = line.split("#", 1)[0].split()
            if not fields:
                continue
            try:
                if len(fields) != 3:
                    raise ValueError("expected 3 fields")
                op, address, size = fields[0].upper(), int(fields[1], 0), int(fields[2], 0)
                if op not in ("R", "W") or address < 0 or size <= 0:
                    raise ValueError("invalid reference")
            except ValueError as exc:
                raise ValueError(f"{path}:{lineno}: {exc}") from exc
            yield op, address, size


def expand_trace(trace: Iterable, block_size: int):
    return [(block, op == "W") for op, addr, size in trace
            for block in range(addr // block_size, (addr + size - 1) // block_size + 1)]


def simulate(probes, config: Config, warmup: int = 0, classify: bool = False):
    if warmup < 0 or warmup >= len(probes):
        raise ValueError("warmup must leave at least one measured probe")
    cache = Cache(config, classify)
    for i, (block, write) in enumerate(probes):
        if i == warmup and warmup:
            cache.reset_stats()
        cache.probe(block, write)
    return cache.result()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace", type=Path)
    p.add_argument("--capacity", type=int, default=4096, help="data bytes only")
    p.add_argument("--block-size", type=int, default=64)
    p.add_argument("--ways", default="4", help="power of two or 'full'")
    p.add_argument("--policy", choices=["LRU", "FIFO", "Random"], default="LRU")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--warmup", type=int, default=0, help="discard first N line probes")
    p.add_argument("--classify", action="store_true", help="3C using FA-LRU shadow")
    args = p.parse_args()
    ways = args.capacity // args.block_size if args.ways == "full" else int(args.ways)
    config = Config(args.capacity, args.block_size, ways, args.policy, args.seed)
    refs = list(read_trace(args.trace))
    probes = expand_trace(refs, config.block_size)
    result = simulate(probes, config, args.warmup, args.classify)
    print(json.dumps({"config": asdict(config), "input_references": len(refs),
                      "warmup_probes": args.warmup, **result}, indent=2))


if __name__ == "__main__":
    main()
