"""Make counterexamples small enough to debug by hand.

1. shrink_by_size: re-run the generator at smaller size parameters (many seeds per size) and return the
   first failure found at the smallest size. Always produces valid inputs.
2. ddmin_lines: delta debugging on input lines (Zeller's ddmin), keeping a candidate only while the
   failure persists and the input stays valid (validator accepts it, or the brute force runs cleanly).
3. shrink_numbers: replace numeric tokens by smaller values (0, 1, halves) while the failure persists.
Size-based shrinking keeps the input well-formed; ddmin needs a validator to keep counts like 'n'
consistent, so it is applied after size shrinking.
"""
import re

from .engine import Failure


def shrink_by_size(tester, failure, seeds_per_size=200, min_size=1):
    best = failure
    for size in range(min_size, failure.size):
        for k in range(seeds_per_size):
            seed = failure.seed * 1000003 + size * 7919 + k
            inp = tester.generator.generate(seed, size)
            f = tester.check_input(seed, size, inp)[0]
            if f and f.kind == failure.kind:
                f.shrunk = True
                return f
    return best


def _still_fails(tester, inp, kind):
    f = tester.check_input(0, 0, inp)[0]
    if f is None or f.kind != kind:
        return None
    return f


def _valid(tester, inp):
    if tester.validator:
        return tester.validator.run(inp, 10.0).returncode == 0
    if tester.brute:
        r = tester.brute.run(inp, tester.brute_time_limit)
        return r.returncode == 0 and not r.timed_out
    return True


def ddmin_lines(tester, failure, max_rounds=200):
    """Remove chunks of lines while the same kind of failure remains (keeps the first line as a header)."""
    lines = failure.input.rstrip("\n").split("\n")
    header, body = lines[:1], lines[1:]
    n = 2
    rounds = 0
    best = failure
    while len(body) >= 2 and rounds < max_rounds:
        rounds += 1
        chunk = max(1, len(body) // n)
        reduced = False
        for start in range(0, len(body), chunk):
            cand = body[:start] + body[start + chunk:]
            text = "\n".join(header + cand) + "\n"
            if not _valid(tester, text):
                continue
            f = _still_fails(tester, text, failure.kind)
            if f:
                body, best, reduced = cand, f, True
                n = max(n - 1, 2)
                break
        if not reduced:
            if n >= len(body):
                break
            n = min(len(body), n * 2)
    if best is not failure:
        best.seed, best.size, best.shrunk = failure.seed, failure.size, True
    return best


_NUMTOK = re.compile(r"-?\d+")


def shrink_numbers(tester, failure, max_steps=300):
    """Greedily make numbers smaller in absolute value (towards 0/1) while the failure persists."""
    best = failure
    text = failure.input
    steps = 0
    changed = True
    while changed and steps < max_steps:
        changed = False
        for m in list(_NUMTOK.finditer(text)):
            v = int(m.group(0))
            for cand in sorted({0, 1, v // 2, v - 1 if v > 0 else v + 1, -v if v < 0 else v} - {v}, key=abs):
                if abs(cand) >= abs(v) and not (v < 0 and cand >= 0):
                    continue
                steps += 1
                t = text[:m.start()] + str(cand) + text[m.end():]
                if not _valid(tester, t):
                    continue
                f = _still_fails(tester, t, failure.kind)
                if f:
                    text, best, changed = t, f, True
                    break
            if changed or steps >= max_steps:
                break
    if best is not failure:
        best.seed, best.size, best.shrunk = failure.seed, failure.size, True
    return best


def shrink(tester, failure, structural=True):
    """Full pipeline: size first, then lines and numbers (structural steps only with a validator or brute)."""
    if failure.kind in ("brute-crash", "brute-timeout", "invalid"):
        return failure
    f = shrink_by_size(tester, failure)
    if structural and (tester.validator or tester.brute):
        f = ddmin_lines(tester, f)
        f = shrink_numbers(tester, f)
    if f is not failure and not f.shrunk:
        f.shrunk = True
    return f
