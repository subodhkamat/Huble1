
import os
import shutil
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from project_service import BASE_DIR


PROJECT_DIR = Path(BASE_DIR).resolve()
HOST = "127.0.0.1"
PORT = 4173

MAX_LOG_LINES = 500
LOG_BUFFER: deque[str] = deque(maxlen=MAX_LOG_LINES)

_PROCESS: subprocess.Popen[str] | None = None
_LOG_THREAD: threading.Thread | None = None
_LOCK = threading.RLock()
_STARTED_AT: float | None = None


def _find_npm() -> str:
    """Find npm without accepting an executable path from a request."""
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")

    if not npm:
        npm = shutil.which("npm")

    if not npm:
        raise RuntimeError(
            "npm was not found. Install Node.js and restart your terminal."
        )

    return npm


def _validate_project() -> None:
    """Ensure all operations stay inside the generated project."""
    root = PROJECT_DIR.resolve()

    if not root.is_dir():
        raise FileNotFoundError(
            f"Generated project directory does not exist: {root}"
        )

    package_file = root / "package.json"

    if not package_file.is_file():
        raise FileNotFoundError(
            f"package.json was not found in {root}"
        )

    # Refuse a symlinked package.json pointing outside the project.
    if not package_file.resolve().is_relative_to(root):
        raise ValueError("package.json resolves outside the project directory.")


def _append_log(message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    with _LOCK:
        LOG_BUFFER.append(f"[{timestamp}] {message.rstrip()}")


def _read_process_output(process: subprocess.Popen[str]) -> None:
    """Continuously capture output without blocking API requests."""
    try:
        if process.stdout is None:
            return

        for line in process.stdout:
            _append_log(line)

        return_code = process.wait()
        _append_log(f"Development server exited with code {return_code}.")
    except Exception as exc:
        _append_log(f"Log reader error: {exc}")


def get_terminal_status() -> dict[str, Any]:
    with _LOCK:
        process = _PROCESS
        running = process is not None and process.poll() is None

        return {
            "running": running,
            "pid": process.pid if running else None,
            "host": HOST if running else None,
            "port": PORT if running else None,
            "preview_url": (
                f"http://localhost:{PORT}" if running else None
            ),
            "started_at": _STARTED_AT if running else None,
            "logs": list(LOG_BUFFER),
        }


def install_dependencies() -> dict[str, Any]:
    """Run the fixed npm install command for the generated project."""
    _validate_project()

    with _LOCK:
        if _PROCESS is not None and _PROCESS.poll() is None:
            raise RuntimeError(
                "Stop the development server before installing dependencies."
            )

    npm = _find_npm()
    _append_log("Installing project dependencies...")

    command = [npm, "install", "--no-audit", "--no-fund"]

    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=300,
            shell=(os.name == "nt"),
            check=False,
        )
    except subprocess.TimeoutExpired:
        _append_log("Dependency installation timed out after 300 seconds.")
        raise RuntimeError(
            "Dependency installation timed out after 300 seconds."
        )

    output = "\n".join(
        part for part in [result.stdout, result.stderr] if part
    )
    if output:
        for line in output.splitlines()[-100:]:
            _append_log(line)

    if result.returncode != 0:
        raise RuntimeError(
            f"npm install failed with exit code {result.returncode}."
        )

    _append_log("Dependency installation completed.")

    return {
        "success": True,
        "message": "Dependencies installed successfully.",
        "output": output[-12000:],
    }


def start_dev_server() -> dict[str, Any]:
    """Start Vite on the fixed local preview port."""
    global _PROCESS, _LOG_THREAD, _STARTED_AT

    _validate_project()
    npm = _find_npm()

    package_data = (PROJECT_DIR / "package.json").read_text(
        encoding="utf-8"
    )

    import json

    try:
        package = json.loads(package_data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid package.json: {exc}") from exc

    scripts = package.get("scripts", {})
    if not isinstance(scripts, dict) or "dev" not in scripts:
        raise ValueError(
            "package.json must contain a 'dev' script to start the preview."
        )

    if not (PROJECT_DIR / "node_modules").is_dir():
        raise RuntimeError(
            "Dependencies are not installed. Run dependency installation first."
        )

    with _LOCK:
        if _PROCESS is not None and _PROCESS.poll() is None:
            return {
                "success": True,
                "message": "Development server is already running.",
                "preview_url": f"http://localhost:{PORT}",
                "pid": _PROCESS.pid,
            }

        LOG_BUFFER.clear()
        _append_log("Starting generated application...")

        # The command is fixed. No command or arguments come from the user.
        if os.name == "nt":
            command = (
                f'"{npm}" run dev -- --host {HOST} '
                f"--port {PORT} --strictPort"
            )
            process = subprocess.Popen(
                command,
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=True,
            )
        else:
            process = subprocess.Popen(
                [
                    npm,
                    "run",
                    "dev",
                    "--",
                    "--host",
                    HOST,
                    "--port",
                    str(PORT),
                    "--strictPort",
                ],
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
                start_new_session=True,
            )

        _PROCESS = process
        _STARTED_AT = time.time()

        _LOG_THREAD = threading.Thread(
            target=_read_process_output,
            args=(process,),
            daemon=True,
        )
        _LOG_THREAD.start()

    # Catch immediate startup failures instead of always claiming success.
    time.sleep(0.5)
    if process.poll() is not None:
        status = get_terminal_status()
        raise RuntimeError(
            "The development server exited during startup. "
            + "\n".join(status["logs"][-20:])
        )

    return {
        "success": True,
        "message": "Development server started.",
        "preview_url": f"http://localhost:{PORT}",
        "pid": process.pid,
    }


def stop_dev_server() -> dict[str, Any]:
    global _PROCESS, _STARTED_AT

    with _LOCK:
        process = _PROCESS

        if process is None or process.poll() is not None:
            _PROCESS = None
            _STARTED_AT = None
            return {
                "success": True,
                "message": "Development server is not running.",
            }

        _append_log("Stopping development server...")

        try:
            if os.name == "nt":
                # Stop the npm process and its child Node/Vite process.
                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                    shell=False,
                )
            else:
                import signal

                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.TimeoutExpired) as exc:
            _append_log(f"Stop warning: {exc}")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        _PROCESS = None
        _STARTED_AT = None
        _append_log("Development server stopped.")

    return {
        "success": True,
        "message": "Development server stopped.",
    }