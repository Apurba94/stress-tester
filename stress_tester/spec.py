"""A tiny generator language for stress tests, so common inputs need no generator program.

    n = randint(1, SIZE)
    q = randint(1, 3)
    print n, q
    print ints(n, -10, 10)
    repeat q: print randint(1, n), randint(1, n)
    edges = tree_edges(n)
    print edges

Statements (one per line or separated by ';'):
  NAME = EXPR             assignment
  print EXPR[, EXPR...]   output values separated by spaces (lists flattened, list of pairs one per line)
  repeat EXPR: STATEMENT  repeat a single statement
  # comment
Expressions are Python expressions over: SIZE (current size parameter), the variables assigned so far,
randint, choice, uniform, the helpers of stress_tester.rnd (ints, perm, distinct, text, tree_edges,
graph_edges, weighted, grid, intervals, partition, sorted_ints) without the rng argument, and
min, max, abs, len, range, sum, sorted, list, str, int, round, LETTERS, DIGITS.
"""
import functools
import re

from . import rnd

SAFE_BUILTINS = {"min": min, "max": max, "abs": abs, "len": len, "range": range, "sum": sum, "sorted": sorted,
                 "list": list, "str": str, "int": int, "round": round, "set": set, "tuple": tuple, "reversed": reversed,
                 "True": True, "False": False, "None": None}


class SpecError(ValueError):
    pass


def _split(text):
    stmts = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            stmts += [s.strip() for s in _split_semicolons(line) if s.strip()]
    return stmts


def _split_semicolons(line):
    """Split on ';' outside quotes and brackets."""
    parts, depth, quote, cur = [], 0, None, ""
    for ch in line:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ";" and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    parts.append(cur)
    return parts


def _split_spaces(text):
    """Split on whitespace outside quotes and brackets."""
    parts, depth, quote, cur = [], 0, None, ""
    for ch in text:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch.isspace() and depth == 0:
            if cur:
                parts.append(cur)
            cur = ""
            continue
        cur += ch
    if cur:
        parts.append(cur)
    return parts


_ASSIGN = re.compile(r"^([A-Za-z_]\w*)\s*=(?!=)\s*(.+)$")
_REPEAT = re.compile(r"^repeat\s+(.+?)\s*:\s*(.+)$")


class SpecGenerator:
    kind = "spec"

    def __init__(self, text):
        self.text = text
        self.statements = _split(text)
        if not self.statements:
            raise SpecError("empty generator spec")
        for s in self.statements:          # compile early so syntax errors appear before stress testing
            self._compile_stmt(s)

    def _compile_stmt(self, s):
        m = _REPEAT.match(s)
        if m:
            return ("repeat", self._expr(m.group(1)), self._compile_stmt(m.group(2)))
        if s.startswith("print"):
            body = s[5:].strip()
            if body.startswith("(") and body.endswith(")") and body.count("(") == 1:
                body = body[1:-1]
            if not body:
                return ("print", None)
            try:
                return ("print", compile("(" + body + ",)", "<spec>", "eval"))
            except SyntaxError:
                # also allow space-separated items: print n m  /  print 1 2 3
                return ("print", self._expr("(" + ", ".join(_split_spaces(body)) + ",)"))
        m = _ASSIGN.match(s)
        if m:
            return ("assign", m.group(1), self._expr(m.group(2)))
        raise SpecError("cannot understand statement %r" % s)

    @staticmethod
    def _expr(src):
        try:
            return compile(src, "<spec>", "eval")
        except SyntaxError as exc:
            raise SpecError("syntax error in %r: %s" % (src, exc.msg))

    def generate(self, seed, size=10):
        rng = rnd.make_rng(seed)
        env = dict(SAFE_BUILTINS)
        env.update({name: functools.partial(fn, rng) for name, fn in rnd.HELPERS.items()})
        env.update({"randint": rng.randint, "choice": rng.choice, "uniform": rng.uniform, "shuffle": rng.shuffle,
                    "sample": rng.sample, "SIZE": size, "LETTERS": rnd.LETTERS, "DIGITS": rnd.DIGITS})
        out = []
        for s in self.statements:
            self._exec(self._compile_stmt(s), env, out)
        return "\n".join(out) + "\n"

    def _exec(self, node, env, out):
        kind = node[0]
        if kind == "assign":
            env[node[1]] = self._eval(node[2], env)
        elif kind == "print":
            vals = self._eval(node[1], env) if node[1] else ()
            out.append(rnd.fmt(*vals) if vals else "")
        else:
            times = self._eval(node[1], env)
            for _ in range(int(times)):
                self._exec(node[2], env, out)

    @staticmethod
    def _eval(code, env):
        try:
            return eval(code, {"__builtins__": {}}, env)
        except Exception as exc:
            raise SpecError("error evaluating generator expression: %s: %s" % (type(exc).__name__, exc))
