"""Analytical and differential validation, independent timestamp reference model."""
from dataclasses import asdict
from pathlib import Path
import random
import tempfile
import unittest
from cache_sim import Cache, Config, read_trace, expand_trace, simulate


def reference(probes, c):
    """Deliberately different implementation: explicit slots and timestamps."""
    slots = [[None] * c.ways for _ in range(c.sets)]
    rng = random.Random(c.seed)
    counts = dict(hits=0, misses=0, evictions=0, writebacks=0,
                  reads=0, writes=0, read_misses=0, write_misses=0)
    for time, (block, write) in enumerate(probes):
        group = slots[block % c.sets]
        match = next((i for i, line in enumerate(group)
                      if line is not None and line[0] == block), None)
        counts["writes" if write else "reads"] += 1
        if match is not None:
            counts["hits"] += 1
            group[match][2] = time
            group[match][3] |= write
            continue
        counts["misses"] += 1
        counts["write_misses" if write else "read_misses"] += 1
        free = next((i for i, line in enumerate(group) if line is None), None)
        if free is None:
            if c.policy == "Random":
                free = rng.randrange(c.ways)
            else:
                field = 2 if c.policy == "LRU" else 1
                free = min(range(c.ways), key=lambda i: group[i][field])
            counts["evictions"] += 1
            counts["writebacks"] += int(group[free][3])
        group[free] = [block, time, time, write]
    counts["resident_dirty_lines"] = sum(int(line[3]) for g in slots for line in g if line)
    return counts


class CacheTests(unittest.TestCase):
    def test_invalid_config(self):
        for args in [dict(capacity=0), dict(block_size=3), dict(ways=3),
                     dict(capacity=64, block_size=64, ways=2), dict(policy="bad")]:
            with self.assertRaises(ValueError):
                Config(**args)

    def test_address_decomposition(self):
        c = Cache(Config(256, 16, 4))
        self.assertEqual(c.config.sets, 4)
        self.assertEqual(c.access("R", 0), [False])
        self.assertEqual(c.access("R", 12), [True])
        self.assertEqual(c.access("R", 16), [False])
        self.assertEqual(list(c.lines[0]), [0])
        self.assertEqual(list(c.lines[1]), [1])

    def test_direct_conflict(self):
        c = Cache(Config(128, 64, 1))
        self.assertEqual([c.access("R", x)[0] for x in [0, 128, 0, 128]],
                         [False] * 4)

    def test_two_way_fits(self):
        c = Cache(Config(128, 64, 2))
        self.assertEqual([c.access("R", x)[0] for x in [0, 128, 0, 128]],
                         [False, False, True, True])

    def test_lru_fifo_difference(self):
        trace = [(b, False) for b in [0, 1, 0, 2, 0]]
        self.assertEqual(simulate(trace, Config(2, 1, 2, "LRU"))["hits"], 2)
        self.assertEqual(simulate(trace, Config(2, 1, 2, "FIFO"))["hits"], 1)

    def test_write_allocate_and_dirty_eviction(self):
        c = Cache(Config(64, 64, 1))
        self.assertEqual(c.access("W", 0), [False])
        self.assertEqual(c.access("R", 4), [True])
        c.access("R", 64)
        self.assertEqual(c.stats.writebacks, 1)
        self.assertEqual(c.result()["resident_dirty_lines"], 0)
        self.assertEqual(c.result()["memory_read_bytes"], 128)

    def test_write_hit_marks_dirty(self):
        c = Cache(Config(64, 64, 1))
        c.access("R", 0)
        c.access("W", 0)
        c.access("R", 64)
        self.assertEqual(c.stats.writebacks, 1)

    def test_split_access(self):
        c = Cache(Config(128, 64, 1))
        self.assertEqual(c.access("W", 62, 4), [False, False])
        self.assertEqual(c.access("R", 63, 2), [True, True])
        self.assertEqual(c.stats.accesses, 4)
        self.assertEqual(c.result()["resident_dirty_lines"], 2)

    def test_random_repeatability(self):
        p = [(i % 7, False) for i in range(1000)]
        cfg = Config(4, 1, 4, "Random", 42)
        self.assertEqual(simulate(p, cfg), simulate(p, cfg))

    def test_direct_policy_equivalence(self):
        p = [(i % 7, bool(i % 2)) for i in range(100)]
        results = [simulate(p, Config(4, 1, 1, policy)) for policy in ["LRU", "FIFO", "Random"]]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])

    def test_3c_hand_calculation(self):
        # Cache has two direct-mapped lines. 0 and 2 conflict.
        c = Cache(Config(2, 1, 1), classify=True)
        for block in [0, 2, 0, 1, 2]:
            c.probe(block)
        self.assertEqual((c.stats.compulsory, c.stats.capacity, c.stats.conflict), (3, 1, 1))
        self.assertEqual(c.stats.misses, 5)

    def test_warmup_preserves_state(self):
        p = [(0, True), (1, False), (0, False), (2, False)]
        r = simulate(p, Config(2, 1, 1), warmup=2, classify=True)
        self.assertEqual((r["accesses"], r["hits"], r["misses"]), (2, 1, 1))
        self.assertEqual(r["compulsory"], 1)
        self.assertEqual(r["writebacks"], 1)
        with self.assertRaises(ValueError):
            simulate(p, Config(2, 1, 1), warmup=4)

    def test_parser_and_comments(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.trace"
            p.write_text("# comment\nR 0x10 4\nw 20 8 # note\n")
            self.assertEqual(list(read_trace(p)), [("R", 16, 4), ("W", 20, 8)])
            p.write_text("R nonsense 4\n")
            with self.assertRaisesRegex(ValueError, ":1:"):
                list(read_trace(p))

    def test_sequential_analytic(self):
        refs = [("R", i, 4) for i in range(0, 65536, 4)]
        p = expand_trace(refs, 64)
        for ways in [1, 2, 4, 8, 64]:
            r = simulate(p, Config(4096, 64, ways), classify=True)
            self.assertEqual(r["misses"], 1024)
            self.assertEqual(r["hit_rate"], 15 / 16)

    def test_associativity_is_not_monotone_for_every_trace(self):
        # More flexible replacement can lose useful partition protection.
        p = [(i % 65, False) for i in range(65 * 4)]
        dm = simulate(p, Config(4096, 64, 1))
        fa = simulate(p, Config(4096, 64, 64))
        self.assertGreater(dm["hits"], fa["hits"])
        self.assertEqual(fa["hits"], 0)

    def test_differential_oracle(self):
        # 3 policies * 2 capacities * 4 associativities * 5 streams = 120 cases.
        for capacity in [32, 64]:
            for ways in [1, 2, 4, capacity // 4]:
                for policy in ["LRU", "FIFO", "Random"]:
                    for seed in range(5):
                        rng = random.Random(seed + 7919)
                        probes = [(rng.randrange(48), rng.random() < .3) for _ in range(600)]
                        cfg = Config(capacity, 4, ways, policy, seed)
                        actual, expected = simulate(probes, cfg), reference(probes, cfg)
                        with self.subTest(config=asdict(cfg)):
                            for key, value in expected.items():
                                self.assertEqual(actual[key], value, key)
                            self.assertEqual(actual["hits"] + actual["misses"], len(probes))


if __name__ == "__main__":
    unittest.main(verbosity=2)
