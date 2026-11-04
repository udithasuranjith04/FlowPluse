"""Start both localhost services and tear them down together on exit."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    os.chdir(ROOT)
    settings = Settings()
    if settings.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("The development launcher only binds to localhost.")
    if settings.port != 8000:
        raise SystemExit(
            "Use port 8000 or update frontend/vite.config.ts before changing the port."
        )
    processes = []

    def stop(*_args):
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    settings.host,
                    "--port",
                    str(settings.port),
                    "--no-access-log",
                    "--ws-max-size",
                    "65536",
                ],
                cwd=ROOT,
            )
        )
        processes.append(
            subprocess.Popen(
                ["npm", "run", "dev", "--", "--port", "5173", "--strictPort"],
                cwd=ROOT / "frontend",
            )
        )
        print(
            "FlowPulse AI: http://127.0.0.1:5173 | API: http://127.0.0.1:8000/docs",
            flush=True,
        )
        while all(process.poll() is None for process in processes):
            time.sleep(0.3)
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
