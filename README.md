# stress-tester

**Find the test that breaks your solution: run it against a brute force on thousands of random inputs,
catch wrong answers, crashes and timeouts, and automatically shrink the counterexample to the smallest
input that still fails.**

Part of the *Competitive Programming Suite* (10 large automation tools for algorithmic problem solving).

## Why

"Wrong answer on test 23" with hidden tests is the most frustrating moment in a contest. The standard
remedy is stress testing: a slow but obviously correct brute force, a random generator, and a loop that
compares the two. Writing that loop, the generator and the shrinking by hand every time costs exactly the
minutes you do not have. `stress-tester` does all of it, and hands you a 2-line counterexample instead of
a 300-line one.

## Features

| Area | Details |
|------|---------|
| Generators | a one-line **spec language** (`n = randint(1, SIZE); print n; print ints(n, -10, 10)`), a Python file with `generate(rng, size)`, or any program called as `gen SEED SIZE` |
| Random structures | ints, distinct values, permutations, strings, sorted arrays, trees (random, line, star, binary, caterpillar), simple/connected/directed graphs, weighted edges, grids, intervals, compositions |
| Programs | Python, C/C++, Rust, Go, Java, JavaScript or any command; compiled once and cached; `--fast` runs Python in-process (about 100x faster) |
| Detection | wrong answers, crashes (with the exception line), timeouts, brute-force crashes (generator/brute bugs), validator rejections; `--crash-only` mode needs no brute force |
| Comparison | tokens, exact, lines, `float:EPS`, or `prog:CHECKER` when several answers are valid |
| Shrinking | 1) smaller size parameters (always valid inputs), 2) delta debugging on lines, 3) smaller numbers; steps 2-3 keep inputs valid via `--validator` or the brute force |
| Workflow | size schedules (`-s 1:10`, `-s 1,5,50`), parallel jobs, time budget, reproducible seeds, failing tests saved as `.in/.out/.got`, JSON results |

## Usage

```bash
pip install .
stress-tester run sol.cpp brute.py -g "n = randint(1, SIZE); print n; print ints(n, -10, 10)" -s 1:8 -n 5000
stress-tester run sol.py brute.py -g gen.spec --fast --save failing/
stress-tester run sol.py brute.py -g gen.py -j 8 --validator validate.py --compare float:1e-6
stress-tester run sol.py -g gen.spec --crash-only -s 200000 -t 1      # look for crashes/TLE on big inputs
stress-tester gen gen.spec --seed 3 -s 5 -k 3                          # inspect generated tests
```

A spec file for a graph problem:

```
n = randint(2, SIZE)
m = randint(n - 1, min(n * (n - 1) // 2, 3 * n))
print n, m
print weighted(graph_edges(n, m, connected=True), 1, 100)
q = randint(1, 5)
print q
repeat q: print randint(1, n), randint(1, n)
```

```python
from stress_tester import StressTester, SpecGenerator, InProcessProgram, shrink
t = StressTester(InProcessProgram("sol.py"), SpecGenerator(spec), InProcessProgram("brute.py"), sizes=range(1, 9))
stats = t.run(5000)
if stats.failures:
    print(shrink(t, stats.failures[0]).input)
```

## Limitations

`--fast` cannot enforce time limits (an infinite loop hangs the run). Structural shrinking without a
validator relies on the brute force rejecting malformed inputs by crashing.

## Testing

```bash
python -m unittest discover -s tests -t .
```

## License

MIT (c) JANIN A APURBA
