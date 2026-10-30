"""Random structure helpers shared by spec generators and Python generator files.

Every function takes an explicit random.Random instance so tests are reproducible from a seed.
"""
import random
import string as _string


def ints(rng, k, lo, hi):
    return [rng.randint(lo, hi) for _ in range(k)]


def distinct(rng, k, lo, hi):
    if hi - lo + 1 < k:
        raise ValueError("cannot draw %d distinct values from [%d, %d]" % (k, lo, hi))
    if hi - lo + 1 <= 4 * k:
        return rng.sample(range(lo, hi + 1), k)
    seen = set()
    while len(seen) < k:
        seen.add(rng.randint(lo, hi))
    out = list(seen)
    rng.shuffle(out)
    return out


def perm(rng, n, start=1):
    p = list(range(start, start + n))
    rng.shuffle(p)
    return p


def text(rng, k, alphabet="abcdefghijklmnopqrstuvwxyz"):
    return "".join(rng.choice(alphabet) for _ in range(k))


def sorted_ints(rng, k, lo, hi, strict=False):
    return sorted(distinct(rng, k, lo, hi) if strict else ints(rng, k, lo, hi))


def tree_edges(rng, n, shape="random", start=1):
    """Edges of a tree on n vertices. shape: random | line | star | caterpillar | binary."""
    if n <= 1:
        return []
    labels = perm(rng, n, start)
    edges = []
    for v in range(1, n):
        if shape == "line":
            p = v - 1
        elif shape == "star":
            p = 0
        elif shape == "binary":
            p = (v - 1) // 2
        elif shape == "caterpillar":
            spine = max(1, n // 2)
            p = v - 1 if v < spine else rng.randrange(spine)
        else:
            p = rng.randrange(v)
        edges.append((labels[p], labels[v]))
    rng.shuffle(edges)
    return [(a, b) if rng.random() < 0.5 else (b, a) for a, b in edges]


def graph_edges(rng, n, m, connected=False, directed=False, self_loops=False, multi=False, start=1):
    """m edges on n vertices; simple by default; connected=True first builds a spanning tree."""
    max_m = n * (n - 1) // (1 if directed else 2) + (n if self_loops else 0)
    if not multi and m > max_m:
        raise ValueError("a simple graph on %d vertices has at most %d edges" % (n, max_m))
    if connected and m < n - 1:
        raise ValueError("a connected graph on %d vertices needs at least %d edges" % (n, n - 1))
    edges, seen = [], set()

    def key(a, b):
        return (a, b) if directed else (min(a, b), max(a, b))
    if connected:
        for a, b in tree_edges(rng, n, start=start):
            edges.append((a, b))
            seen.add(key(a, b))
    while len(edges) < m:
        a, b = rng.randint(start, start + n - 1), rng.randint(start, start + n - 1)
        if a == b and not self_loops:
            continue
        if not multi and key(a, b) in seen:
            continue
        seen.add(key(a, b))
        edges.append((a, b))
    rng.shuffle(edges)
    return edges


def weighted(rng, edges, lo, hi):
    return [(a, b, rng.randint(lo, hi)) for a, b in edges]


def grid(rng, rows, cols, chars=".#", weights=None):
    return ["".join(rng.choices(chars, weights=weights, k=cols)) for _ in range(rows)]


def intervals(rng, k, lo, hi):
    out = []
    for _ in range(k):
        a, b = rng.randint(lo, hi), rng.randint(lo, hi)
        out.append((min(a, b), max(a, b)))
    return out


def partition(rng, total, parts, min_part=1):
    """Random composition of total into `parts` integers each >= min_part."""
    if parts * min_part > total:
        raise ValueError("cannot split %d into %d parts of at least %d" % (total, parts, min_part))
    free = total - parts * min_part
    cuts = sorted(rng.randint(0, free) for _ in range(parts - 1))
    pieces = [b - a for a, b in zip([0] + cuts, cuts + [free])]
    return [p + min_part for p in pieces]


def fmt(*items):
    """Format values the usual way: lists/tuples space-separated, nested lists one per line."""
    out = []
    for it in items:
        if isinstance(it, (list, tuple)) and it and isinstance(it[0], (list, tuple)):
            out.append("\n".join(" ".join(map(str, row)) for row in it))
        elif isinstance(it, (list, tuple)):
            out.append(" ".join(map(str, it)))
        else:
            out.append(str(it))
    return " ".join(out) if not any("\n" in o for o in out) else "\n".join(out)


HELPERS = {
    "ints": ints, "distinct": distinct, "perm": perm, "text": text, "sorted_ints": sorted_ints,
    "tree_edges": tree_edges, "graph_edges": graph_edges, "weighted": weighted, "grid": grid,
    "intervals": intervals, "partition": partition,
}
LETTERS = _string.ascii_lowercase
DIGITS = _string.digits


def make_rng(seed):
    return random.Random(seed)
