import os
import tempfile

# Maximum subarray sum. The buggy Kadane starts from 0 and fails when every number is negative.
BRUTE = """n = int(input())
a = list(map(int, input().split()))
print(max(sum(a[i:j]) for i in range(n) for j in range(i + 1, n + 1)))
"""
BUGGY = """n = int(input())
a = list(map(int, input().split()))
best = cur = 0
for x in a:
    cur = max(0, cur + x)
    best = max(best, cur)
print(best)
"""
CORRECT = """n = int(input())
a = list(map(int, input().split()))
best = cur = a[0]
for x in a[1:]:
    cur = max(x, cur + x)
    best = max(best, cur)
print(best)
"""
CRASHER = """n = int(input())
a = list(map(int, input().split()))
print(a[n // 2 + 3] if n > 4 else sum(a))
"""
SLOW = """import time
n = int(input())
if n > 3:
    time.sleep(5)
print(0)
"""
VALIDATOR = """import sys
lines = sys.stdin.read().split("\\n")
n = int(lines[0])
a = lines[1].split()
assert 1 <= n == len(a), "n does not match"
"""
SPEC = "n = randint(1, SIZE)\nprint n\nprint ints(n, -10, 10)\n"
PY_GEN = """def generate(rng, size):
    n = rng.randint(1, size)
    return [n, [rng.randint(-10, 10) for _ in range(n)]]
"""
PROG_GEN = """import random, sys
seed, size = int(sys.argv[1]), int(sys.argv[2])
rng = random.Random(seed)
n = rng.randint(1, size)
print(n)
print(*[rng.randint(-10, 10) for _ in range(n)])
"""


class Workspace:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        for name, text in (("brute.py", BRUTE), ("buggy.py", BUGGY), ("correct.py", CORRECT), ("crash.py", CRASHER),
                           ("slow.py", SLOW), ("validator.py", VALIDATOR), ("gen.spec", SPEC), ("pygen.py", PY_GEN),
                           ("proggen.py", PROG_GEN)):
            self.write(name, text)

    def write(self, name, text):
        p = os.path.join(self.root, name)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return p

    def path(self, name):
        return os.path.join(self.root, name)

    def close(self):
        self.tmp.cleanup()
