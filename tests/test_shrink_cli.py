import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from stress_tester.cli import main, parse_sizes
from stress_tester.engine import Failure, StressTester
from stress_tester.programs import InProcessProgram
from stress_tester.shrink import ddmin_lines, shrink, shrink_by_size, shrink_numbers
from stress_tester.spec import SpecGenerator

from .helpers import SPEC, Workspace


class ShrinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def make_tester(self, validator=True):
        f = lambda n: InProcessProgram(self.ws.path(n))
        return StressTester(f("buggy.py"), SpecGenerator(SPEC), f("brute.py"),
                            validator=f("validator.py") if validator else None, sizes=[30])

    def test_shrink_by_size_reaches_one(self):
        t = self.make_tester()
        failure = t.run(500).failures[0]
        small = shrink_by_size(t, failure)
        self.assertEqual(small.size, 1)
        self.assertEqual(small.input.split("\n")[0], "1")
        self.assertTrue(small.shrunk)

    def test_ddmin_and_numbers_on_handmade_input(self):
        # a format where lines are independent queries: buggy fails only on the query "-7"
        body = "\n".join(["5", "3", "-7", "2", "9", "4", "8"]) + "\n"
        q_brute = self.ws.write("qb.py", "import sys\nfor x in sys.stdin.read().split()[1:]:\n    print(int(x))\n")
        q_bug = self.ws.write("qbug.py", "import sys\nfor x in sys.stdin.read().split()[1:]:\n    print(max(0, int(x)))\n")
        t = StressTester(InProcessProgram(q_bug), SpecGenerator("print 1"), InProcessProgram(q_brute))
        f0 = t.check_input(1, 7, body)[0]
        self.assertEqual(f0.kind, "mismatch")
        f1 = ddmin_lines(t, f0)
        self.assertEqual(f1.input.strip().split("\n"), ["5", "-7"])
        f2 = shrink_numbers(t, f1)
        self.assertEqual(f2.input.strip().split("\n"), ["0", "-1"])

    def test_full_pipeline_and_untouched_kinds(self):
        t = self.make_tester()
        f = shrink(t, t.run(500).failures[0])
        self.assertEqual(f.input.strip().split("\n")[0], "1")
        b = Failure("brute-crash", 1, 5, "x")
        self.assertIs(shrink(t, b), b)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_parse_sizes(self):
        self.assertEqual(parse_sizes("5"), [5])
        self.assertEqual(parse_sizes("1:4"), [1, 2, 3, 4])
        self.assertEqual(parse_sizes("2:10:4"), [2, 6, 10])
        self.assertEqual(parse_sizes("1,5,9"), [1, 5, 9])

    def test_run_finds_and_saves(self):
        save, js = os.path.join(self.ws.root, "fails"), os.path.join(self.ws.root, "r.json")
        with redirect_stdout(io.StringIO()) as buf, redirect_stderr(io.StringIO()):
            code = main(["run", self.ws.path("buggy.py"), self.ws.path("brute.py"), "-g", self.ws.path("gen.spec"),
                         "-s", "1:6", "--fast", "--save", save, "--json", js])
        self.assertEqual(code, 1)
        out = buf.getvalue()
        self.assertIn("FAILED: wrong answer", out)
        self.assertIn("[shrunk]", out)
        self.assertTrue(any(f.endswith(".in") for f in os.listdir(save)))
        with open(js) as fh:
            self.assertEqual(len(json.load(fh)["failures"]), 1)

    def test_run_ok_and_gen(self):
        with redirect_stdout(io.StringIO()) as buf, redirect_stderr(io.StringIO()):
            self.assertEqual(main(["run", self.ws.path("correct.py"), self.ws.path("brute.py"), "-g", self.ws.path("gen.spec"),
                                   "-n", "100", "--fast", "-q"]), 0)
            self.assertEqual(main(["gen", "n = 3; print n; print perm(n)", "-k", "2"]), 0)
        self.assertIn("OK: no difference found", buf.getvalue())
        self.assertIn("# seed 2", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
