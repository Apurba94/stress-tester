import random
import unittest

from stress_tester import rnd
from stress_tester.spec import SpecError, SpecGenerator


class SpecTests(unittest.TestCase):
    def test_deterministic_and_size(self):
        g = SpecGenerator("n = randint(1, SIZE)\nprint n\nprint ints(n, -5, 5)")
        a, b = g.generate(7, 6), g.generate(7, 6)
        self.assertEqual(a, b)
        lines = a.strip().split("\n")
        n = int(lines[0])
        self.assertTrue(1 <= n <= 6)
        self.assertEqual(len(lines[1].split()), n)
        self.assertNotEqual(g.generate(1, 50), g.generate(2, 50))

    def test_repeat_semicolons_and_pairs(self):
        g = SpecGenerator("n = 5; q = 3; print n, q; repeat q: print randint(1, n), randint(1, n)\nprint tree_edges(n)")
        lines = g.generate(3).strip().split("\n")
        self.assertEqual(lines[0], "5 3")
        self.assertEqual(len(lines), 1 + 3 + 4)
        self.assertTrue(all(len(l.split()) == 2 for l in lines[1:]))

    def test_print_parentheses_strings_and_builtins(self):
        g = SpecGenerator('s = text(4, "ab"); print(len(s)); print s; print max(3, 9), "x;y"')
        out = g.generate(1).split("\n")
        self.assertEqual(out[0], "4")
        self.assertTrue(set(out[1]) <= {"a", "b"})
        self.assertEqual(out[2], "9 x;y")

    def test_errors(self):
        with self.assertRaises(SpecError):
            SpecGenerator("")
        with self.assertRaises(SpecError):
            SpecGenerator("n = (")
        with self.assertRaises(SpecError):
            SpecGenerator("this is not valid")
        with self.assertRaises(SpecError):
            SpecGenerator("print undefined_name").generate(1)
        with self.assertRaises(SpecError):
            SpecGenerator("print __import__('os')").generate(1)     # no builtins available


class RndTests(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(5)

    def _connected(self, n, edges):
        parent = list(range(n + 1))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for a, b in edges:
            parent[find(a)] = find(b)
        return len({find(v) for v in range(1, n + 1)}) == 1

    def test_trees(self):
        for shape in ("random", "line", "star", "binary", "caterpillar"):
            e = rnd.tree_edges(self.rng, 30, shape)
            self.assertEqual(len(e), 29)
            self.assertTrue(self._connected(30, e), shape)
        degrees = {}
        for a, b in rnd.tree_edges(self.rng, 10, "star"):
            degrees[a] = degrees.get(a, 0) + 1
            degrees[b] = degrees.get(b, 0) + 1
        self.assertEqual(max(degrees.values()), 9)

    def test_graphs(self):
        e = rnd.graph_edges(self.rng, 8, 20, connected=True)
        self.assertEqual(len(e), 20)
        self.assertEqual(len({(min(a, b), max(a, b)) for a, b in e}), 20)
        self.assertTrue(self._connected(8, e))
        self.assertTrue(all(a != b for a, b in e))
        with self.assertRaises(ValueError):
            rnd.graph_edges(self.rng, 4, 7)
        d = rnd.graph_edges(self.rng, 3, 6, directed=True)
        self.assertEqual(len(set(d)), 6)

    def test_misc(self):
        self.assertEqual(sorted(rnd.perm(self.rng, 6)), [1, 2, 3, 4, 5, 6])
        self.assertEqual(len(set(rnd.distinct(self.rng, 50, 1, 60))), 50)
        p = rnd.partition(self.rng, 20, 4, 2)
        self.assertEqual((sum(p), len(p), min(p) >= 2), (20, 4, True))
        self.assertEqual(rnd.fmt([(1, 2), (3, 4)]), "1 2\n3 4")
        self.assertEqual(rnd.fmt(3, [1, 2]), "3 1 2")
        g = rnd.grid(self.rng, 3, 4)
        self.assertEqual([len(r) for r in g], [4, 4, 4])
        self.assertTrue(all(a <= b for a, b in rnd.intervals(self.rng, 10, 1, 100)))


if __name__ == "__main__":
    unittest.main()
