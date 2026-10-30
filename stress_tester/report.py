"""Human-readable reports and reproduction commands for stress-test results."""
import json
from dataclasses import asdict


def _block(title, text, limit=1500):
    text = text if len(text) <= limit else text[:limit] + "\n... (%d more characters)" % (len(text) - limit)
    return "%s:\n%s" % (title, "\n".join("    " + l for l in text.rstrip("\n").split("\n")))


def failure_text(f):
    parts = ["FAILED: " + f.describe() + (" [shrunk]" if f.shrunk else ""), _block("input", f.input)]
    if f.kind in ("mismatch", "brute-crash"):
        parts += [_block("solution output", f.output or "(empty)"), _block("expected (brute)", f.expected or "(empty)")]
    elif f.kind in ("crash", "timeout") and f.output:
        parts.append(_block("partial output", f.output))
    return "\n".join(parts)


def summary(stats):
    s = "%d tests in %.1fs (%.0f tests/s); slowest solution run %.3fs, slowest brute run %.3fs" % (
        stats.tests, stats.seconds, stats.rate, stats.max_solution_time, stats.max_brute_time)
    if not stats.failures:
        return "OK: no difference found. " + s
    return "%d failure(s). %s" % (len(stats.failures), s)


def reproduce_command(args_line, failure):
    return "%s --start %d --iterations 1 --size %d" % (args_line, failure.seed, failure.size)


def to_json(stats):
    return json.dumps({"tests": stats.tests, "seconds": stats.seconds, "sizes": stats.sizes,
                       "max_solution_time": stats.max_solution_time, "max_brute_time": stats.max_brute_time,
                       "failures": [asdict(f) for f in stats.failures]}, indent=2)
