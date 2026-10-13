
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from runtime_service import install_runtime_bridge
from project_service import BASE_DIR


# Local development preview configuration.

# Vite preview configuration
PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = "5173"
PREVIEW_URL = f"http://{PREVIEW_HOST}:{PREVIEW_PORT}"

_process = None


def start_preview() -> str:
    install_runtime_bridge()
    global _proces
    print("1")
    project_dir = Path(BASE_DIR).resolve()
    print(f"{project_dir}")
    package_file = project_dir / "package.json"
    entry_file = project_dir / "index.html"
    print(f"{package_file}")
    print(f"{entry_file}")
    if not package_file.is_file() or not entry_file.is_file():
        raise ValueError(
            "Generated project is missing package.json or index.html."
        )
    print("3")

   
    npm = "npm.cmd" if os.name == "nt" else "npm"

    # Install dependencies without running package lifecycle scripts.
    install = subprocess.run(
        [npm, "install", "--ignore-scripts"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=180,
        shell=False,
    )
    print("3")
    if install.returncode != 0:
        raise RuntimeError(
            "Dependency installation failed: "
            + install.stderr[-2000:]
        )
    print("3")
    print("npm:", repr(npm), type(npm))
    print("project_dir:", repr(project_dir), type(project_dir))

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

    for i, arg in enumerate(command):
     print(f"command[{i}]: {repr(arg)} | {type(arg)}")

    print("cwd:", repr(project_dir), type(project_dir))

    _process = subprocess.Popen(
        [
            npm,
            "run",
            "dev",
            "--",
            "--host", PREVIEW_HOST,
            "--port", str(PREVIEW_PORT),
            "--strictPort",
        ],
        cwd=str(project_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )

    print(f"{_process}")
    print("5")
    # Wait for Vite to become reachable.
    for _ in range(100):
            if _process.poll() is not None:
                raise RuntimeError("The Vite preview process exited.")
    
            if _is_ready():
                return PREVIEW_URL
    
            time.sleep(0.5)
    
    raise RuntimeError(
            "Preview did not start within 20 seconds."
        )


def _is_ready() -> bool:
    try:
        with urllib.request.urlopen(
            PREVIEW_URL,
            timeout=12,
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False