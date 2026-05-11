#!/usr/bin/env python3
"""
Conduit startup script — works on Windows, macOS, and Linux.

Starts the backend (FastAPI / uvicorn) and frontend (Vite / npm) together
in the same terminal window with colour-coded, prefixed output.

Usage:
    python start.py            # start both services
    python start.py --backend  # backend only
    python start.py --frontend # frontend only

Press Ctrl+C to stop everything cleanly.
"""

import argparse
import os
import platform
import subprocess
import sys
import threading
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent
BACKEND_DIR  = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

# ── ANSI colours (disabled automatically on Windows without a terminal) ───────

IS_WINDOWS = platform.system() == "Windows"

def _supports_colour():
    if IS_WINDOWS:
        # Windows 10 1511+ supports ANSI if ENABLE_VIRTUAL_TERMINAL_PROCESSING is set.
        # os.system("") is the simplest way to activate it.
        os.system("")
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOUR = _supports_colour()

RESET  = "\033[0m"  if USE_COLOUR else ""
BOLD   = "\033[1m"  if USE_COLOUR else ""
DIM    = "\033[2m"  if USE_COLOUR else ""
CYAN   = "\033[96m" if USE_COLOUR else ""
GREEN  = "\033[92m" if USE_COLOUR else ""
YELLOW = "\033[93m" if USE_COLOUR else ""
RED    = "\033[91m" if USE_COLOUR else ""
GRAY   = "\033[90m" if USE_COLOUR else ""

# ── Helpers ───────────────────────────────────────────────────────────────────

def find_executable(names):
    """Return the first executable found in PATH, or None."""
    import shutil
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def stream(proc, label, colour):
    """
    Read lines from *proc* stdout/stderr and print them with a coloured prefix.
    Runs in a daemon thread — exits when the process ends.
    """
    prefix = f"{colour}{BOLD}[{label}]{RESET} "
    try:
        for raw in proc.stdout:
            line = raw.rstrip("\n").rstrip("\r\n")
            print(f"{prefix}{line}", flush=True)
    except Exception:
        pass


def start_process(cmd, cwd, env=None):
    """Spawn a subprocess that merges stderr into stdout."""
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env or os.environ.copy(),
        # On Windows, CREATE_NEW_PROCESS_GROUP lets us send Ctrl+C to the child
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0,
    )


# ── Service launchers ─────────────────────────────────────────────────────────

def launch_backend():
    python = sys.executable  # same interpreter that's running this script
    cmd = [python, "-m", "uvicorn", "app.main:app",
           "--host", "0.0.0.0", "--port", "8000", "--reload"]
    print(f"{CYAN}{BOLD}[backend]{RESET} Starting on {BOLD}http://localhost:8000{RESET}")
    return start_process(cmd, BACKEND_DIR)


def launch_frontend():
    npm = find_executable(["npm", "npm.cmd"])  # npm.cmd is the Windows shim
    if npm is None:
        print(f"{RED}[frontend] npm not found — is Node.js installed?{RESET}")
        return None
    cmd = [npm, "run", "dev"]
    print(f"{GREEN}{BOLD}[frontend]{RESET} Starting on {BOLD}http://localhost:5173{RESET}")
    return start_process(cmd, FRONTEND_DIR)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Start Conduit services")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--backend",  action="store_true", help="Start backend only")
    group.add_argument("--frontend", action="store_true", help="Start frontend only")
    args = parser.parse_args()

    run_backend  = not args.frontend
    run_frontend = not args.backend

    print(f"\n{BOLD}  Conduit{RESET} — starting services\n")

    procs = []

    if run_backend:
        be = launch_backend()
        if be:
            procs.append(be)
            t = threading.Thread(target=stream, args=(be, "backend", CYAN), daemon=True)
            t.start()

    if run_frontend:
        fe = launch_frontend()
        if fe:
            procs.append(fe)
            t = threading.Thread(target=stream, args=(fe, "frontend", GREEN), daemon=True)
            t.start()

    if not procs:
        print(f"{RED}No services started — nothing to do.{RESET}")
        sys.exit(1)

    print(f"\n{DIM}  Press Ctrl+C to stop all services{RESET}\n")

    try:
        # Wait until any process exits (e.g. a crash) or Ctrl+C is pressed
        while True:
            for p in procs:
                ret = p.poll()
                if ret is not None:
                    label = "backend" if p == procs[0] and run_backend else "frontend"
                    print(f"\n{YELLOW}[{label}] Process exited with code {ret}{RESET}")
                    raise KeyboardInterrupt
            threading.Event().wait(0.5)

    except KeyboardInterrupt:
        print(f"\n{BOLD}Stopping services…{RESET}")
        for p in procs:
            if p.poll() is None:
                try:
                    if IS_WINDOWS:
                        p.send_signal(__import__("signal").CTRL_BREAK_EVENT)
                    else:
                        p.terminate()
                except Exception:
                    pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print(f"{BOLD}All services stopped.{RESET}\n")


if __name__ == "__main__":
    main()
