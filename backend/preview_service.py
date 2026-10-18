
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
import sys
from runtime_service import install_runtime_bridge
from project_service import BASE_DIR


PREVIEW_HOST = "0.0.0.0"
PREVIEW_PORT = 5173
PREVIEW_URL = f"http://127.0.0.1:{PREVIEW_PORT}/preview/"

_process = None
_log_file = None
_current_project = None


def repair_linux_rollup_dependency(
    project_dir: Path,
    npm: str | None = None,
) -> None:
    """Repair missing Rollup Linux native dependencies on Render."""
    if not sys.platform.startswith("linux"):
        return

    node_modules = project_dir / "node_modules"
    rollup_loader = node_modules / "rollup" / "dist" / "native.js"
    native_dir = node_modules / "@rollup" / "rollup-linux-x64-gnu"

    # Rollup is not installed yet; the normal npm install below handles it.
    if not rollup_loader.is_file():
        return

    # The package must contain both its manifest and native binary.
    native_package_json = native_dir / "package.json"
    native_binary = native_dir / "rollup.linux-x64-gnu.node"

    if native_package_json.is_file() and native_binary.is_file():
        print("Linux Rollup native dependency is present.")
        return

    npm = npm or shutil.which("npm")
    if not npm:
        raise RuntimeError(
            "npm is required to repair the missing Linux Rollup dependency."
        )

    print("Missing Linux Rollup native dependency detected.")
    print("Reinstalling generated-project dependencies...")

    # Remove platform-specific installed files and the potentially
    # incomplete lockfile so npm can resolve optional dependencies again.
    shutil.rmtree(node_modules, ignore_errors=True)

    lockfile = project_dir / "package-lock.json"
    if lockfile.exists():
        lockfile.unlink()

    try:
        result = subprocess.run(
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
            "npm install timed out while repairing Rollup after 300 seconds."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Could not reinstall generated-project dependencies: {exc}"
        ) from exc

    print("npm repair exit code:", result.returncode)
    if result.stdout:
        print("npm output:", result.stdout[-4000:])
    if result.stderr:
        print("npm errors:", result.stderr[-4000:])

    if result.returncode != 0:
        raise RuntimeError(
            "Dependency repair failed:\n"
            + (result.stderr or result.stdout or "")[-5000:]
        )

    if not (
        native_package_json.is_file()
        and native_binary.is_file()
    ):
        raise RuntimeError(
            "npm install completed, but Rollup's Linux native binary "
            "is still missing."
        )

    print("Linux Rollup dependency repaired successfully.")




def start_preview() -> str:
    global _process, _log_file, _current_project

    print("Installing runtime bridge...")
    install_runtime_bridge()

    project_dir = Path(BASE_DIR).resolve()
    package_file = project_dir / "package.json"
    index_file = project_dir / "index.html"
    main_file = project_dir / "src" / "main.jsx"
    
    print("Preview project:", project_dir)
    
    print("Preview project:", project_dir)
    print("package.json:", package_file.is_file())
    print("index.html:", index_file.is_file())
    print("src/main.jsx:", main_file.is_file())

    if not package_file.is_file() or not index_file.is_file():
        raise ValueError(
            f"Generated project is missing package.json or index.html: "
            f"{project_dir}"
        )

    if not main_file.is_file():
        raise ValueError(
            f"Generated project is missing src/main.jsx: {main_file}"
        )

    node = shutil.which("node")
    npm = shutil.which("npm")

    if os.name == "nt" and not npm:
        npm = shutil.which("npm.cmd")

    if not node:
        raise RuntimeError("Node.js was not found in PATH.")

    # Repair an incomplete Linux Rollup installation before launching Vite.
    repair_linux_rollup_dependency(project_dir, npm)

    vite_js = project_dir / "node_modules" / "vite" / "bin" / "vite.js"

    if not vite_js.is_file():
        if not npm:
            raise RuntimeError("npm was not found in PATH.")

        print("Vite is missing. Installing dependencies...")

        try:
            result = subprocess.run(
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
                "npm install timed out after 300 seconds."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Could not run npm install: {exc}"
            ) from exc

        print("npm exit code:", result.returncode)
        print("npm output:", (result.stdout or "")[-3000:])
        print("npm errors:", (result.stderr or "")[-3000:])

        if result.returncode != 0:
            raise RuntimeError(
                "npm install failed:\n"
                + (result.stderr or result.stdout or "")[-5000:]
            )

    if not vite_js.is_file():
        raise RuntimeError(f"Vite executable not found: {vite_js}")

        try:
            result = subprocess.run(
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
                "npm install timed out after 300 seconds."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Could not run npm install: {exc}"
            ) from exc

        print("npm exit code:", result.returncode)
        print("npm output:", (result.stdout or "")[-3000:])
        print("npm errors:", (result.stderr or "")[-3000:])

        if result.returncode != 0:
            raise RuntimeError(
                "npm install failed:\n"
                + (result.stderr or result.stdout or "")[-5000:]
            )

    if not vite_js.is_file():
        raise RuntimeError(f"Vite executable not found: {vite_js}")

    # Reuse the server only if the homepage AND JavaScript entry work.
    if _process is not None and _process.poll() is None:
        if _current_project == project_dir and _is_ready():
            print("Existing Vite preview is healthy.")
            return PREVIEW_URL

        print("Stopping unhealthy or outdated preview...")
        _stop_process()

    log_path = project_dir / "vite-preview.log"

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

    print("Starting Vite:", command)

    try:
        _process = subprocess.Popen(
            command,
            cwd=str(project_dir),
            stdout=_log_file,
            stderr=subprocess.STDOUT,
            shell=False,
        )
    except OSError as exc:
        _close_log()
        raise RuntimeError(f"Could not start Vite: {exc}") from exc

    _current_project = project_dir
    print("Vite PID:", _process.pid)

    deadline = time.monotonic() + 45

    while time.monotonic() < deadline:
        exit_code = _process.poll()

        if exit_code is not None:
            logs = _read_preview_logs(project_dir)
            _stop_process()
            raise RuntimeError(
                f"Vite exited with code {exit_code}.\n{logs}"
            )

        if _is_ready():
            print("Vite preview is healthy:", PREVIEW_URL)
            return PREVIEW_URL

        time.sleep(1)

    logs = _read_preview_logs(project_dir)
    _stop_process()

    raise RuntimeError(
        "Vite did not serve the JavaScript entry correctly "
        "within 45 seconds.\n" + logs
    )



def _is_ready() -> bool:
    """Check that Vite serves HTML and transformed JavaScript correctly."""
    try:
        with urllib.request.urlopen(PREVIEW_URL, timeout=3) as response:
            if response.status != 200:
                return False

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type.lower():
                return False

        for relative_path in ("src/main.jsx", "src/App.jsx"):
            url = PREVIEW_URL + relative_path
            request = urllib.request.Request(
                url,
                headers={"Accept": "text/javascript, */*"},
            )

            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status != 200:
                    return False

                content_type = response.headers.get("Content-Type", "")
                body = response.read(4000).decode(
                    "utf-8", errors="replace"
                ).lstrip()

                if "text/html" in content_type.lower():
                    print(
                        f"Preview check failed: {relative_path} returned HTML."
                    )
                    return False

                if body.lower().startswith(
                    ("<!doctype html", "<html", "<head", "<body")
                ):
                    print(
                        f"Preview check failed: {relative_path} returned HTML."
                    )
                    return False

        return True

    except (
        OSError,
        urllib.error.URLError,
        TimeoutError,
    ) as exc:
        print("Preview health check:", str(exc))
        return False



def _stop_process() -> None:
    global _process, _current_project

    if _process is not None and _process.poll() is None:
        _process.terminate()

        try:
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()
            _process.wait()

    _process = None
    _current_project = None
    _close_log()


def _close_log() -> None:
    global _log_file

    if _log_file is not None:
        if not _log_file.closed:
            _log_file.close()
        _log_file = None


def _read_preview_logs(project_dir: Path) -> str:
    if _log_file is not None and not _log_file.closed:
        _log_file.flush()

    log_path = project_dir / "vite-preview.log"

    try:
        logs = log_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        return f"\nVite logs ({log_path}):\n{logs[-8000:]}"

    except OSError as exc:
        return f"\nCould not read Vite logs: {exc}"
