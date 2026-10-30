"""The stress-testing loop: generate, run both programs, compare, collect failures."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

KINDS = ("mismatch", "crash", "timeout", "brute-crash", "brute-timeout", "invalid")


@dataclass
class Failure:
    kind: str                 # one of KINDS
    seed: int
    size: int
    input: str
    output: str = ""
    expected: str = ""
    message: str = ""
    shrunk: bool = False

    def describe(self):
        head = {"mismatch": "wrong answer", "crash": "solution crashed", "timeout": "solution too slow",
                "brute-crash": "BRUTE FORCE crashed (check the brute or the generator)",
                "brute-timeout": "brute force too slow (lower --size)", "invalid": "validator rejected the input"}[self.kind]
        return "%s (seed %d, size %d)%s" % (head, self.seed, self.size, ": " + self.message if self.message else "")


@dataclass
class StressStats:
    tests: int = 0
    failures: list = field(default_factory=list)
    seconds: float = 0.0
    max_solution_time: float = 0.0
    max_brute_time: float = 0.0
    sizes: list = field(default_factory=list)

    @property
    def rate(self):
        return self.tests / self.seconds if self.seconds else 0.0


class StressTester:
    """Run `solution` against `brute` on generated tests.

    sizes: list of size parameters cycled through (small first finds simpler counterexamples).
    validator: optional Program that must exit 0 on valid inputs.
    mode: 'compare' (needs brute) or 'crash' (only look for runtime errors / timeouts in the solution)."""

    def __init__(self, solution, generator, brute=None, compare=None, validator=None, time_limit=2.0,
                 brute_time_limit=10.0, sizes=(5,), jobs=1, mode=None):
        from .compare import get_comparator
        self.solution, self.brute, self.generator = solution, brute, generator
        self.compare = compare if callable(compare) else get_comparator(compare or "tokens")
        self.validator = validator
        self.time_limit, self.brute_time_limit = time_limit, brute_time_limit
        self.sizes = list(sizes) or [5]
        self.jobs = max(1, jobs)
        self.mode = mode or ("compare" if brute else "crash")
        if self.mode == "compare" and not brute:
            raise ValueError("compare mode needs a brute-force program")

    def check_input(self, seed, size, inp):
        """Return a Failure or None (with timings) for one generated input."""
        if self.validator:
            v = self.validator.run(inp, 10.0)
            if v.returncode != 0:
                return Failure("invalid", seed, size, inp, message=(v.stderr or v.stdout).strip()[:200]), 0, 0
        s = self.solution.run(inp, self.time_limit)
        if s.timed_out:
            return Failure("timeout", seed, size, inp, s.stdout, message="> %.2fs" % self.time_limit), s.seconds, 0
        if s.returncode != 0:
            last = s.stderr.strip().splitlines()[-1:] or [""]
            return Failure("crash", seed, size, inp, s.stdout, message="exit %s %s" % (s.returncode, last[0][:150])), s.seconds, 0
        if self.mode == "crash":
            return None, s.seconds, 0
        b = self.brute.run(inp, self.brute_time_limit)
        if b.timed_out:
            return Failure("brute-timeout", seed, size, inp, s.stdout), s.seconds, b.seconds
        if b.returncode != 0:
            return Failure("brute-crash", seed, size, inp, s.stdout, b.stdout, b.stderr.strip()[-200:]), s.seconds, b.seconds
        ok, msg = self.compare(inp, s.stdout, b.stdout)
        if not ok:
            return Failure("mismatch", seed, size, inp, s.stdout, b.stdout, msg), s.seconds, b.seconds
        return None, s.seconds, b.seconds

    def _one(self, seed):
        size = self.sizes[seed % len(self.sizes)]
        inp = self.generator.generate(seed, size)
        return (seed, size) + self.check_input(seed, size, inp)

    def run(self, iterations=1000, start_seed=1, max_failures=1, time_budget=None, progress=None):
        for p in (self.solution, self.brute, self.validator):
            if p:
                p.compile()
        stats = StressStats(sizes=self.sizes)
        t0 = time.perf_counter()
        seeds = iter(range(start_seed, start_seed + iterations))

        def record(item):
            seed, size, failure, ts, tb = item
            stats.tests += 1
            stats.max_solution_time = max(stats.max_solution_time, ts)
            stats.max_brute_time = max(stats.max_brute_time, tb)
            if failure:
                stats.failures.append(failure)
            if progress:
                progress(stats, failure)

        def done():
            return len(stats.failures) >= max_failures or \
                (time_budget is not None and time.perf_counter() - t0 > time_budget)

        if self.jobs == 1:
            for seed in seeds:
                record(self._one(seed))
                if done():
                    break
        else:
            with ThreadPoolExecutor(self.jobs) as ex:
                while not done():
                    batch = [s for _, s in zip(range(self.jobs * 4), seeds)]
                    if not batch:
                        break
                    for item in ex.map(self._one, batch):
                        record(item)
                        if done():
                            break
            stats.failures.sort(key=lambda f: f.seed)
            stats.failures = stats.failures[:max_failures] if max_failures else stats.failures
        stats.seconds = time.perf_counter() - t0
        return stats


def save_failure(folder, failure, index=1):
    os.makedirs(folder, exist_ok=True)
    stem = os.path.join(folder, "fail%02d_seed%d" % (index, failure.seed))
    with open(stem + ".in", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(failure.input)
    if failure.expected:
        with open(stem + ".out", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(failure.expected)
    with open(stem + ".got", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(failure.output)
    return stem + ".in"
