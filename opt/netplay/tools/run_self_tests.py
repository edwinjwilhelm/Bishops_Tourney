#!/usr/bin/env python3
"""
Run Bishops_Golden.py self-tests with a friendly summary.

Usage:
  python tools/run_self_tests.py           # runs 'all'
  python tools/run_self_tests.py all       # runs full suite
  python tools/run_self_tests.py ai3       # run a specific test
  python tools/run_self_tests.py corners_view

Exit codes mirror the Golden file:
  0 = PASS, 1 = WARN, 2 = FAIL, 3 = EXCEPTION/UNKNOWN
"""
import os
import sys
import subprocess
from typing import List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
GOLDEN = os.path.join(ROOT, 'Bishops_Golden.py')


def _python_exe() -> str:
    return sys.executable or 'python'


def run(selector: str = 'all') -> int:
    if not os.path.exists(GOLDEN):
        print(f"[ERROR] Golden engine not found: {GOLDEN}")
        return 3
    cmd: List[str] = [_python_exe(), GOLDEN]
    if selector:
        if selector == 'all':
            cmd.append('--self-test=all')
        else:
            cmd.append(f'--self-test={selector}')
    env = os.environ.copy()
    print(f"[RUN] {' '.join(cmd)}\n")
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    except KeyboardInterrupt:
        print("[INTERRUPTED]")
        return 3
    # Echo captured output
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        # Keep stderr separate but visible
        print(proc.stderr.rstrip(), file=sys.stderr)
    code = proc.returncode
    status = {0: 'PASS', 1: 'WARN', 2: 'FAIL', 3: 'ERROR'}.get(code, f'RC={code}')
    print(f"\n[SUMMARY] selector={selector} -> {status} (exit {code})")
    return code


def main():
    sel = 'all'
    if len(sys.argv) >= 2:
        sel = sys.argv[1].strip()
    sys.exit(run(sel))


if __name__ == '__main__':
    main()
