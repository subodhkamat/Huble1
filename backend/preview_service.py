
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from runtime_service import install_runtime_bridge
from project_service import BASE_DIR

PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = 5173
PREVIEW_URL = f"http://{PREVIEW_HOST}:{PREVIEW_PORT}"

_process = None
_log_file = None


def start_preview() -> str:
    global _process, _log_file

    print("1: Installing runtime bridge...")
    install_runtime_bridge()
    print("1a: Runtime bridge installed successfully")

    project_dir = Path(BASE_DIR).resolve()
    package_file = project_dir / "package.json"
    entry_file = project_dir / "index.html"

    print("2: Project directory:", project_dir)
    print("2a: Package file:", package_file)
    print("2b: Entry file:", entry_file)
    print("2c: Package exists:", package_file.is_file())
    print("2d: Index exists:", entry_file.is_file())

    if not package_file.is_file() or not entry_file.is_file():
        raise ValueError(
            "Generated project is missing package.json or index.html."
        )

    print("3: Checking previous Vite process...")

    if _process is not None and _process.poll() is None:
        print("3a: Existing process PID:", _process.pid)

        if _is_ready():
            print("3b: Existing preview is already ready")
            return PREVIEW_URL

        print("3c: Existing process is not ready; terminating")
        _process.terminate()

        try:
            _process.wait(timeout=5)
            print("3d: Existing process terminated")
        except subprocess.TimeoutExpired:
            print("3e: Force killing existing process")
            _process.kill()
            _process.wait()

    npm = "npm.cmd" if os.name == "nt" else "npm"
    print("4: npm executable:", repr(npm))

    
    print("5: Installing dependencies...")

    try:
        install = subprocess.run(
            [
                npm,
                "install",
                "--include=dev",
                "--no-audit",
                "--no-fund",
            ],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=300,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Dependency installation exceeded 300 seconds."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Could not run npm install: {exc}"
        ) from exc

    print("5c: npm install return code:", install.returncode)
    print("5d: npm stdout:", (install.stdout or "")[-3000:])
    print("5e: npm stderr:", (install.stderr or "")[-3000:])

    if install.returncode != 0:
        raise RuntimeError(
            "Dependency installation failed:\n"
            f"{(install.stderr or install.stdout or '')[-5000:]}"
        )

    vite_path = project_dir / "node_modules" / ".bin" / "vite"

    if not vite_path.exists():
        raise RuntimeError(
            "Vite is still missing after npm install. "
            "Check package.json and the npm installation logs."
        )

    print("6: Dependencies installed and Vite verified.")


    log_path = project_dir / "vite-preview.log"
    print("6a: Vite log file:", log_path)

    if _log_file is not None and not _log_file.closed:
        _log_file.close()

    _log_file = open(log_path, "w", encoding="utf-8")

    command = [
        npm,
        "run",
        "dev",
        "--",
        "--host",
        PREVIEW_HOST,
        "--port",
        str(PREVIEW_PORT),
        "--strictPort",
    ]
          
    print("7: Starting Vite...")
    print("7a: Command:", repr(command))
    print("7b: Working directory:", repr(str(project_dir)))

    try:
        _process = subprocess.Popen(
            command,
            cwd=str(project_dir),
            stdout=_log_file,
            stderr=subprocess.STDOUT,
            shell=False,
        )
    except OSError as exc:
        print("7c: Failed to launch Vite:", repr(exc))
        _log_file.close()
        _log_file = None
        raise RuntimeError(
            f"Could not launch npm. Is Node.js installed? {exc}"
        ) from exc

    print("8: Vite process started")
    print("8a: Process PID:", _process.pid)

    deadline = time.monotonic() + 30
    attempt = 0

    print("9: Waiting for Vite to become ready...")

    while time.monotonic() < deadline:
        attempt += 1
        process_status = _process.poll()

        print(
            f"9.{attempt}: Polling Vite | "
            f"PID={_process.pid} | "
            f"exit_code={process_status}"
        )

        if process_status is not None:
            print("9a: Vite process exited unexpectedly")
            print("9b: Reading Vite logs...")

            raise RuntimeError(
                "Vite exited during startup.\n"
                + _read_preview_logs(project_dir)
            )

        if _is_ready():
            print("10: Vite preview is ready")
            print("10a: Preview URL:", PREVIEW_URL)
            return PREVIEW_URL

        time.sleep(0.5)

    print("11: Vite startup timed out")
    raise RuntimeError(
        "Vite did not become ready within 30 seconds.\n"
        + _read_preview_logs(project_dir)
    )


def _is_ready() -> bool:
    try:
        print("CHECK: Requesting preview URL:", PREVIEW_URL)

        with urllib.request.urlopen(
            PREVIEW_URL,
            timeout=1,
        ) as response:
            print("CHECK: HTTP status:", response.status)
            return response.status == 200

    except (OSError, urllib.error.URLError) as exc:
        print("CHECK: Preview not ready:", repr(exc))
        return False


def _read_preview_logs(project_dir: Path) -> str:
    global _log_file

    print("LOGS: Flushing Vite output...")

    if _log_file is not None and not _log_file.closed:
        _log_file.flush()

    log_path = project_dir / "vite-preview.log"
    print("LOGS: Reading:", log_path)

    try:
        logs = log_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        print("LOGS: Contents:\n", logs[-8000:])

        return f"Vite logs ({log_path}):\n{logs[-8000:]}"

    except OSError as exc:
        print("LOGS: Could not read file:", repr(exc))
        return f"Could not read Vite logs: {exc}"
