
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from runtime_service import install_runtime_bridge
from project_service import BASE_DIR


PREVIEW_HOST = "0.0.0.0"
PREVIEW_PORT = 5173
PREVIEW_URL = f"http://127.0.0.1:{PREVIEW_PORT}/preview/"

_process = None
_log_file = None
_current_project = None


def start_preview() -> str:
    global _process, _log_file, _current_project

    print("1: Installing runtime bridge...")
    install_runtime_bridge()
    print("1a: Runtime bridge installed successfully")

    project_dir = Path(BASE_DIR).resolve()
    package_file = project_dir / "package.json"
    entry_file = project_dir / "index.html"

    print("2: Project directory:", project_dir)
    print("2a: package.json exists:", package_file.is_file())
    print("2b: index.html exists:", entry_file.is_file())

    if not package_file.is_file() or not entry_file.is_file():
        raise ValueError(
            "Generated project is missing package.json or index.html."
        )

    node = shutil.which("node")
    npm = shutil.which("npm")

    if os.name == "nt" and not npm:
        npm = shutil.which("npm.cmd")

    if not node or not npm:
        raise RuntimeError(
            f"Node.js/npm not found in PATH. node={node}, npm={npm}"
        )

    vite_js = project_dir / "node_modules" / "vite" / "bin" / "vite.js"

    # Reinstall dependencies if Vite is missing.
    if not vite_js.is_file():
        print("3: Vite missing; installing project dependencies...")

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
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Dependency installation exceeded 300 seconds."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Could not run npm install: {exc}"
            ) from exc

        print("npm install exit code:", install.returncode)
        print("npm stdout:", (install.stdout or "")[-3000:])
        print("npm stderr:", (install.stderr or "")[-3000:])

        if install.returncode != 0:
            raise RuntimeError(
                "Dependency installation failed:\n"
                f"{(install.stderr or install.stdout or '')[-5000:]}"
            )

    if not vite_js.is_file():
        raise RuntimeError(
            f"Vite entry point not found after installation: {vite_js}"
        )

    # Reuse a running process only if it belongs to this project.
    same_project = _current_project == project_dir

    if _process is not None and _process.poll() is None:
        if same_project and _is_ready():
            print("4: Existing preview is ready.")
            return PREVIEW_URL

        print("4: Stopping previous preview process...")
        _process.terminate()

        try:
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()
            _process.wait()

    log_path = project_dir / "vite-preview.log"

    if _log_file is not None and not _log_file.closed:
        _log_file.close()

    _log_file = open(log_path, "w", encoding="utf-8")

    command = [
        node,
        str(vite_js),
        "--host",
        PREVIEW_HOST,
        "--port",
        str(PREVIEW_PORT),
        "--strictPort",
        "--base",
        "/preview/",
    ]

    print("5: Starting Vite:", command)

    try:
        _process = subprocess.Popen(
            command,
            cwd=str(project_dir),
            stdout=_log_file,
            stderr=subprocess.STDOUT,
            shell=False,
        )
    except OSError as exc:
        _log_file.close()
        _log_file = None
        raise RuntimeError(
            f"Could not start Vite: {exc}"
        ) from exc

    _current_project = project_dir
    print("6: Vite PID:", _process.pid)

    deadline = time.monotonic() + 30

    while time.monotonic() < deadline:
        exit_code = _process.poll()

        if exit_code is not None:
            raise RuntimeError(
                f"Vite exited with code {exit_code}.\n"
                + _read_preview_logs(project_dir)
            )

        if _is_ready():
            print("7: Preview is ready:", PREVIEW_URL)
            return PREVIEW_URL

        time.sleep(0.5)

    raise RuntimeError(
        "Vite did not become ready within 30 seconds.\n"
        + _read_preview_logs(project_dir)
    )


def _is_ready() -> bool:
    try:
        with urllib.request.urlopen(
            PREVIEW_URL,
            timeout=2,
        ) as response:
            return response.status == 200

    except (OSError, urllib.error.URLError):
        return False


def _read_preview_logs(project_dir: Path) -> str:
    if _log_file is not None and not _log_file.closed:
        _log_file.flush()

    log_path = project_dir / "vite-preview.log"

    try:
        logs = log_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        return f"Vite logs ({log_path}):\n{logs[-8000:]}"

    except OSError as exc:
        return f"Could not read Vite logs: {exc}"
