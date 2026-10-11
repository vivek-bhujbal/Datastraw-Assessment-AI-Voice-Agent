"""Run the frontend, backend and public WebSocket proxy in one container."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def main():
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    frontend_port = 3001 if port == 3000 else 3000
    backend_port = 8001 if port == 8000 else 8000
    if not os.environ.get("FRONTEND_ORIGINS", "").strip():
        raise ValueError("Set FRONTEND_ORIGINS to the public frontend HTTPS origin before deployment")
    config = Path("/tmp/aura-nginx.conf")
    template = (ROOT / "deployment/nginx.conf.template").read_text(encoding="utf-8")
    config.write_text(
        template.replace("__PORT__", str(port))
        .replace("__FRONTEND_PORT__", str(frontend_port))
        .replace("__BACKEND_PORT__", str(backend_port)),
        encoding="utf-8",
    )
    stopping = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopping.set())
    children = []
    try:
        children.append(subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
            "--port", str(backend_port), "--ws-max-size", "5000000",
            "--ws-ping-interval", "20", "--ws-ping-timeout", "20",
        ], cwd=ROOT / "backend"))
        children.append(subprocess.Popen(
            ["node", "server.js"], cwd=ROOT / "frontend",
            env={**os.environ, "HOSTNAME": "127.0.0.1", "PORT": str(frontend_port)},
        ))
        deadline = time.monotonic() + 60
        pending = {f"http://127.0.0.1:{backend_port}/health", f"http://127.0.0.1:{frontend_port}/"}
        while pending and not stopping.is_set():
            if any(child.poll() is not None for child in children):
                raise RuntimeError("An application service exited during startup")
            if time.monotonic() >= deadline:
                raise RuntimeError("Application services did not become ready within 60 seconds")
            for url in tuple(pending):
                try:
                    with urllib.request.urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            pending.remove(url)
                except (urllib.error.URLError, TimeoutError):
                    pass
            if pending:
                stopping.wait(0.25)
        if not stopping.is_set():
            children.append(subprocess.Popen(["nginx", "-c", str(config), "-g", "daemon off;"]))
            print(f"Frontend and backend ready; listening on port {port}", flush=True)
        while not stopping.wait(0.5):
            if any(child.poll() is not None for child in children):
                raise RuntimeError("An application service exited; restarting the container is required")
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
