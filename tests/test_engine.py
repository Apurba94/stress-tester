import unittest

from stress_tester.engine import StressTester
from stress_tester.generators import ProgramGenerator, PythonFunctionGenerator, make_generator
from stress_tester.programs import InProcessProgram, Program
from stress_tester.spec import SpecGenerator

from .helpers import SPEC, Workspace


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        cls.gen = SpecGenerator(SPEC)

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def fast(self, name):
        return InProcessProgram(self.ws.path(name))

    def test_finds_mismatch_in_process(self):
        t = StressTester(self.fast("buggy.py"), self.gen, self.fast("brute.py"), sizes=range(1, 8))
        stats = t.run(2000)
        self.assertEqual(len(stats.failures), 1)
        f = stats.failures[0]
        self.assertEqual(f.kind, "mismatch")
        self.assertTrue(all(int(x) < 0 for x in f.input.split("\n")[1].split()))   # all negative, as expected
        self.assertLess(stats.tests, 2000)

    def test_correct_solution_passes(self):
        stats = StressTester(self.fast("correct.py"), self.gen, self.fast("brute.py"), sizes=[1, 3, 8]).run(300)
        self.assertEqual((stats.failures, stats.tests), ([], 300))

    def test_crash_only_mode(self):
        stats = StressTester(self.fast("crash.py"), self.gen, sizes=[10]).run(200)
        self.assertEqual(stats.failures[0].kind, "crash")
        self.assertIn("IndexError", stats.failures[0].message)

    def test_timeout_subprocess(self):
        t = StressTester(Program(self.ws.path("slow.py")), SpecGenerator("print 5; print 1 2 3 4 5"),
                         Program(self.ws.path("brute.py")), time_limit=0.5)
        self.assertEqual(t.run(3).failures[0].kind, "timeout")

    def test_brute_crash_reported(self):
        self.ws.write("brute_bad.py", "n = int(input())\nprint([1, 2][n])\n")
        t = StressTester(self.fast("correct.py"), SpecGenerator("print 3; print 1 2 3"), self.fast("brute_bad.py"))
        f = t.run(5).failures[0]
        self.assertEqual(f.kind, "brute-crash")
        self.assertIn("BRUTE", f.describe())

    def test_validator_rejects(self):
        t = StressTester(self.fast("correct.py"), SpecGenerator("print 4; print 1 2"), self.fast("brute.py"),
                         validator=self.fast("validator.py"))
        self.assertEqual(t.run(3).failures[0].kind, "invalid")

    def test_parallel_subprocess(self):
        t = StressTester(Program(self.ws.path("buggy.py")), self.gen, Program(self.ws.path("brute.py")),
                         sizes=[1, 2], jobs=4)
        stats = t.run(120, max_failures=2)
        self.assertGreaterEqual(len(stats.failures), 1)
        self.assertEqual(stats.failures, sorted(stats.failures, key=lambda f: f.seed))

    def test_float_compare(self):
        a = self.ws.write("third.py", "print(int(input()) / 3)\n")
        b = self.ws.write("third_round.py", "print(round(int(input()) / 3, 9))\n")
        gen = SpecGenerator("print randint(1, 1000)")
        self.assertEqual(StressTester(self.fast("third.py"), gen, self.fast("third_round.py"), "float:1e-6").run(50).failures, [])
        self.assertTrue(StressTester(self.fast("third.py"), gen, self.fast("third_round.py"), "exact").run(50).failures)

    def test_generator_kinds(self):
        self.assertIsInstance(make_generator(self.ws.path("pygen.py")), PythonFunctionGenerator)
        self.assertIsInstance(make_generator(self.ws.path("proggen.py")), ProgramGenerator)
        self.assertIsInstance(make_generator(self.ws.path("gen.spec")), SpecGenerator)
        self.assertIsInstance(make_generator("print 1"), SpecGenerator)
        for g in (make_generator(self.ws.path("pygen.py")), make_generator(self.ws.path("proggen.py"))):
            lines = g.generate(4, 6).strip().split("\n")
            self.assertEqual(len(lines[1].split()), int(lines[0]))

    def test_needs_brute_for_compare(self):
        with self.assertRaises(ValueError):
            StressTester(self.fast("correct.py"), self.gen, mode="compare")


if __name__ == "__main__":
    unittest.main()
