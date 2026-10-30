"""Command-line interface for stress-tester."""
import argparse
import sys

from . import report
from .engine import StressTester, save_failure
from .generators import make_generator
from .programs import make_program
from .shrink import shrink


def parse_sizes(text):
    """'10' -> [10]; '1:20' -> 1..20; '1,2,5,10' -> list; '3:30:3' -> range with step."""
    if "," in text:
        return [int(x) for x in text.split(",")]
    if ":" in text:
        parts = [int(x) for x in text.split(":")]
        lo, hi = parts[0], parts[1]
        step = parts[2] if len(parts) > 2 else 1
        return list(range(lo, hi + 1, step))
    return [int(text)]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="stress-tester", description="Find inputs where a solution disagrees with a brute force.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="stress test a solution")
    r.add_argument("solution")
    r.add_argument("brute", nargs="?", help="trusted slow solution (omit with --crash-only)")
    r.add_argument("-g", "--gen", required=True, help="generator: spec file, inline spec, .py with generate(rng, size), or program")
    r.add_argument("-n", "--iterations", type=int, default=1000)
    r.add_argument("-s", "--size", default="1:10", help="size parameter(s): N, LO:HI[:STEP] or a,b,c")
    r.add_argument("--start", type=int, default=1, help="first seed")
    r.add_argument("-j", "--jobs", type=int, default=1)
    r.add_argument("-t", "--time-limit", type=float, default=2.0)
    r.add_argument("--brute-time-limit", type=float, default=10.0)
    r.add_argument("-c", "--compare", default="tokens", help="tokens | exact | lines | float[:EPS] | prog:CHECKER")
    r.add_argument("--validator", help="program that exits 0 for valid inputs")
    r.add_argument("--crash-only", action="store_true", help="only look for crashes and timeouts (no brute force)")
    r.add_argument("--no-shrink", action="store_true")
    r.add_argument("--max-failures", type=int, default=1)
    r.add_argument("--budget", type=float, help="stop after this many seconds")
    r.add_argument("--fast", action="store_true", help="run Python programs in-process (no time limit enforcement)")
    r.add_argument("--save", help="folder for failing tests (.in/.out/.got)")
    r.add_argument("--json", help="write results as JSON")
    r.add_argument("-q", "--quiet", action="store_true")
    g = sub.add_parser("gen", help="print generated tests (to check a generator)")
    g.add_argument("gen")
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("-s", "--size", type=int, default=5)
    g.add_argument("-k", "--count", type=int, default=1)
    args = ap.parse_args(argv)

    if args.cmd == "gen":
        gen = make_generator(args.gen)
        for i in range(args.count):
            if args.count > 1:
                print("# seed %d" % (args.seed + i))
            sys.stdout.write(gen.generate(args.seed + i, args.size))
        return 0

    fast = args.fast and args.jobs == 1
    sol = make_program(args.solution, fast)
    brute = None if args.crash_only or not args.brute else make_program(args.brute, fast)
    validator = make_program(args.validator, fast) if args.validator else None
    tester = StressTester(sol, make_generator(args.gen), brute, args.compare, validator, args.time_limit,
                          args.brute_time_limit, parse_sizes(args.size), args.jobs, "crash" if brute is None else "compare")

    def progress(stats, failure):
        if not args.quiet and (stats.tests % 100 == 0 or failure):
            sys.stderr.write("\r%d tests, %d failure(s)   " % (stats.tests, len(stats.failures)))
            sys.stderr.flush()

    try:
        stats = tester.run(args.iterations, args.start, args.max_failures, args.budget, progress)
    except RuntimeError as exc:
        print("\nerror: %s" % exc, file=sys.stderr)
        return 2
    if not args.quiet:
        sys.stderr.write("\n")
    if stats.failures and not args.no_shrink:
        stats.failures = [shrink(tester, f) for f in stats.failures]
    for i, f in enumerate(stats.failures, 1):
        print(report.failure_text(f))
        if args.save:
            print("saved: %s" % save_failure(args.save, f, i))
    print(report.summary(stats))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(report.to_json(stats))
    return 1 if stats.failures else 0
