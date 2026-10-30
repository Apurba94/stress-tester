"""Test generators: a spec (mini language), a Python file with generate(rng, size), or any program
called as `<program> <seed> <size>` that prints one test to stdout."""
import importlib.util
import os

from . import rnd
from .programs import make_program
from .spec import SpecGenerator


class PythonFunctionGenerator:
    kind = "python"

    def __init__(self, path):
        spec = importlib.util.spec_from_file_location("stress_user_generator", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "generate"):
            raise ValueError("%s has no generate(rng, size) function; it will be run as a program instead" % path)
        self.fn = mod.generate
        self.name = os.path.basename(path)

    def generate(self, seed, size=10):
        out = self.fn(rnd.make_rng(seed), size)
        if isinstance(out, (list, tuple)):
            out = "\n".join(rnd.fmt(x) for x in out)
        out = str(out)
        return out if out.endswith("\n") else out + "\n"


class ProgramGenerator:
    kind = "program"

    def __init__(self, path_or_cmd, timeout=10.0):
        self.program = make_program(path_or_cmd)
        self.name = self.program.name
        self.timeout = timeout

    def generate(self, seed, size=10):
        r = self.program.run("", self.timeout, args=(seed, size))
        if not r.ok:
            raise RuntimeError("generator failed for seed %s (exit %s): %s" % (seed, r.returncode, r.stderr.strip()[-300:]))
        return r.stdout if r.stdout.endswith("\n") else r.stdout + "\n"


def _defines_generate(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return "def generate(" in fh.read()


def make_generator(spec):
    """spec: path to .spec/.gen file, a .py file (generate() function or script), another program, or inline spec text."""
    if os.path.isfile(spec):
        if spec.endswith((".spec", ".gen", ".txt")):
            with open(spec, encoding="utf-8") as fh:
                return SpecGenerator(fh.read())
        if spec.endswith(".py") and _defines_generate(spec):
            return PythonFunctionGenerator(spec)
        return ProgramGenerator(spec)
    return SpecGenerator(spec)
