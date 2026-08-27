"""Findings: the one reporting channel for parser, lint, cuts, and build.

Severity gates the build: ERROR blocks --json (and, in M2, render);
WARN and INFO never do. The parser stays lenient so a single --check
pass reports every problem in the file at once — strictness lives at
the build gate, not in the parser.
"""

from dataclasses import dataclass

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

_ORDER = {ERROR: 0, WARN: 1, INFO: 2}


@dataclass
class Finding:
    severity: str
    code: str
    line: int  # 1-based source line; 0 means "whole file"
    message: str

    def format(self) -> str:
        loc = f"line {self.line:>4}" if self.line else "    file"
        return f"{self.severity:<5} [{self.code}] {loc}: {self.message}"


def has_errors(findings) -> bool:
    return any(f.severity == ERROR for f in findings)


def sorted_findings(findings):
    return sorted(findings, key=lambda f: (f.line, _ORDER.get(f.severity, 9), f.code))


def summarize(findings) -> str:
    e = sum(1 for f in findings if f.severity == ERROR)
    w = sum(1 for f in findings if f.severity == WARN)
    i = sum(1 for f in findings if f.severity == INFO)
    return f"{e} error(s), {w} warning(s), {i} info"
