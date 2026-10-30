"""Output comparison for stress tests: tokens, exact, lines, float tolerance, or a checker program."""
import math
import os
import re
import subprocess
import sys
import tempfile

_NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def tokens(inp, a, b):
    ta, tb = a.split(), b.split()
    if ta == tb:
        return True, ""
    for i, (x, y) in enumerate(zip(ta, tb), 1):
        if x != y:
            return False, "token %d: %r vs %r" % (i, x, y)
    return False, "token count %d vs %d" % (len(ta), len(tb))


def exact(inp, a, b):
    na, nb = a.replace("\r\n", "\n").rstrip("\n"), b.replace("\r\n", "\n").rstrip("\n")
    return (True, "") if na == nb else (False, "outputs differ")


def lines(inp, a, b):
    la = [l.rstrip() for l in a.replace("\r\n", "\n").strip("\n").split("\n")]
    lb = [l.rstrip() for l in b.replace("\r\n", "\n").strip("\n").split("\n")]
    if la == lb:
        return True, ""
    for i, (x, y) in enumerate(zip(la, lb), 1):
        if x != y:
            return False, "line %d differs" % i
    return False, "line count %d vs %d" % (len(la), len(lb))


def make_float(eps):
    def cmp(inp, a, b):
        ta, tb = a.split(), b.split()
        if len(ta) != len(tb):
            return False, "token count %d vs %d" % (len(ta), len(tb))
        for i, (x, y) in enumerate(zip(ta, tb), 1):
            if _NUM.match(x) and _NUM.match(y):
                fx, fy = float(x), float(y)
                if not (abs(fx - fy) <= eps or abs(fx - fy) <= eps * abs(fy) or (math.isnan(fx) and math.isnan(fy))):
                    return False, "token %d: %s vs %s" % (i, x, y)
            elif x != y:
                return False, "token %d: %r vs %r" % (i, x, y)
        return True, ""
    return cmp


def make_checker_program(path):
    """Checker called as: checker input solution_output brute_output -> exit 0 if the solution output is acceptable.

    Needed when several answers are correct (e.g. 'print any valid permutation')."""
    cmd = [sys.executable, path] if path.endswith(".py") else [path]

    def cmp(inp, a, b):
        with tempfile.TemporaryDirectory() as d:
            files = []
            for n, t in (("in.txt", inp), ("out.txt", a), ("ans.txt", b)):
                p = os.path.join(d, n)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(t)
                files.append(p)
            r = subprocess.run(cmd + files, capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stderr or r.stdout).strip()[:200]
    return cmp


def get_comparator(spec="tokens"):
    if spec == "tokens":
        return tokens
    if spec == "exact":
        return exact
    if spec == "lines":
        return lines
    if spec == "float" or spec.startswith("float:"):
        return make_float(float(spec.split(":")[1]) if ":" in spec else 1e-6)
    if spec.startswith("prog:"):
        return make_checker_program(spec[5:])
    raise ValueError("unknown comparison %r" % spec)
