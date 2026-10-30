"""stress-tester: find counterexamples by comparing a solution with a brute force on random tests."""
from .compare import get_comparator
from .engine import Failure, StressStats, StressTester, save_failure
from .generators import PythonFunctionGenerator, ProgramGenerator, make_generator
from .programs import InProcessProgram, Program, make_program
from .shrink import ddmin_lines, shrink, shrink_by_size, shrink_numbers
from .spec import SpecError, SpecGenerator

__version__ = "0.1.0"
__all__ = ["get_comparator", "Failure", "StressStats", "StressTester", "save_failure", "PythonFunctionGenerator",
           "ProgramGenerator", "make_generator", "InProcessProgram", "Program", "make_program", "ddmin_lines", "shrink",
           "shrink_by_size", "shrink_numbers", "SpecError", "SpecGenerator"]
