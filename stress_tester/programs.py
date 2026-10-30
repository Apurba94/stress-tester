"""Running solutions, brute forces, generators and validators: as subprocesses (any language) or, for
Python, in-process (100x faster, for quick stress loops)."""
import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

EXE = ".exe" if os.name == "nt" else ""
LANGS = {
    ".py": (None, ["{python}", "{src}"]),
    ".js": (None, ["node", "{src}"]),
    ".cpp": (["g++", "-std=c++17", "-O2", "{src}", "-o", "{exe}"], ["{exe}"]),
    ".cc": (["g++", "-std=c++17", "-O2", "{src}", "-o", "{exe}"], ["{exe}"]),
    ".c": (["gcc", "-O2", "{src}", "-o", "{exe}", "-lm"], ["{exe}"]),
    ".rs": (["rustc", "-O", "{src}", "-o", "{exe}"], ["{exe}"]),
    ".go": (["go", "build", "-o", "{exe}", "{src}"], ["{exe}"]),
    ".java": (["javac", "-d", "{dir}", "{src}"], ["java", "-cp", "{dir}", "{stem}"]),
}


@dataclass
class Execution:
    returncode: int
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False

    @property
    def ok(self):
        return self.returncode == 0 and not self.timed_out


class Program:
    """A command to run with stdin. Built from a source file (language by extension) or a raw command."""

    def __init__(self, source=None, command=None, build_root=None):
        if not source and not command:
            raise ValueError("need a source file or a command")
        self.source = os.path.abspath(source) if source else None
        self.name = os.path.basename(source) if source else " ".join(command)
        self._command = command
        self.build_root = build_root or os.path.join(tempfile.gettempdir(), "stress-tester-build")
        self.values = {}
        if source:
            ext = os.path.splitext(source)[1].lower()
            if ext not in LANGS:
                raise ValueError("unsupported file type %s (use command=...)" % ext)
            self.compile_cmd, self.run_cmd = LANGS[ext]
            with open(self.source, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()[:16]
            d = os.path.join(self.build_root, digest)
            stem = os.path.splitext(os.path.basename(source))[0]
            self.values = {"src": self.source, "python": sys.executable, "dir": d, "stem": stem,
                           "exe": os.path.join(d, stem + EXE)}
        self.compiled = False

    def compile(self):
        if self._command or self.compiled or not self.compile_cmd:
            self.compiled = True
            return
        os.makedirs(self.values["dir"], exist_ok=True)
        marker = os.path.join(self.values["dir"], ".ok")
        if not os.path.exists(marker):
            cmd = [p.format(**self.values) for p in self.compile_cmd]
            if not shutil.which(cmd[0]):
                raise RuntimeError("compiler %s not found for %s" % (cmd[0], self.name))
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("compilation of %s failed:\n%s" % (self.name, (r.stdout + r.stderr)[-3000:]))
            open(marker, "w").close()
        self.compiled = True

    def command(self, args=()):
        base = list(self._command) if self._command else [p.format(**self.values) for p in self.run_cmd]
        return base + [str(a) for a in args]

    def run(self, stdin="", timeout=5.0, args=()):
        self.compile()
        t0 = time.perf_counter()
        try:
            r = subprocess.run(self.command(args), input=stdin, capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
            return Execution(r.returncode, r.stdout, r.stderr[-4000:], time.perf_counter() - t0)
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            return Execution(-9, out, "timed out", time.perf_counter() - t0, True)


class InProcessProgram:
    """Execute a Python script in this interpreter with redirected stdin/stdout.

    Much faster than a subprocess. No time limit can be enforced, and the script must not call exit()
    in ways that skip output (SystemExit is caught). Not thread-safe: use with one worker."""

    def __init__(self, source):
        self.source = os.path.abspath(source)
        self.name = os.path.basename(source)
        with open(self.source, encoding="utf-8") as fh:
            self.code = compile(fh.read(), self.source, "exec")

    def compile(self):
        pass

    def run(self, stdin="", timeout=None, args=()):
        out, err = io.StringIO(), io.StringIO()
        old_stdin, old_argv = sys.stdin, sys.argv
        sys.stdin, sys.argv = io.StringIO(stdin), [self.source] + [str(a) for a in args]
        t0 = time.perf_counter()
        code = 0
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    exec(self.code, {"__name__": "__main__", "__file__": self.source})
                except SystemExit as exc:
                    code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
                except BaseException as exc:          # noqa: BLE001 - report any crash as a runtime error
                    import traceback
                    err.write("".join(traceback.format_exception_only(type(exc), exc)))
                    code = 1
        finally:
            sys.stdin, sys.argv = old_stdin, old_argv
        return Execution(code, out.getvalue(), err.getvalue()[-4000:], time.perf_counter() - t0)


def make_program(path_or_cmd, in_process=False):
    if isinstance(path_or_cmd, (list, tuple)):
        return Program(command=list(path_or_cmd))
    if in_process and path_or_cmd.endswith(".py"):
        return InProcessProgram(path_or_cmd)
    if os.path.isfile(path_or_cmd):
        return Program(path_or_cmd)
    return Program(command=path_or_cmd.split())
