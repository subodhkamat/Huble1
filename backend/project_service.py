
from pathlib import Path
import os
import zipfile

from pathlib import Path
from tempfile import NamedTemporaryFile

BASE_DIR = (
    Path(__file__).resolve().parent.parent
    / "workspace"
    / "generated_project"
).resolve()


def save_project(files: dict[str, str]) -> str:
    print("1c")
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    print("2c")
    for relative_path, content in files.items():
        target = (BASE_DIR / relative_path).resolve()

        # Defense in depth: make sure the target
        # remains inside the generated project.
        if not target.is_relative_to(BASE_DIR):
            raise ValueError("Unsafe project file path.")

        target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        target.write_text(
            content,
            encoding="utf-8"
        )
    print("3c")
    return str(BASE_DIR)


def create_project_zip() -> Path:
    """
    Create a ZIP of the generated project.

    Excludes dependencies, secrets, Git metadata,
    caches, and build artifacts.
    """
    project_dir = BASE_DIR.resolve()

    if not project_dir.is_dir():
        raise FileNotFoundError(
            "Generated project directory does not exist."
        )

    excluded_dirs = {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
    }

    excluded_files = {
        ".env",
        ".env.local",
        ".env.development.local",
        ".env.production.local",
        ".env.test.local",
    }

    fd, zip_name = __import__("tempfile").mkstemp(
        prefix="ai-project-",
        suffix=".zip",
    )
    os.close(fd)

    zip_path = Path(zip_name)

    try:
        file_count = 0

        with zipfile.ZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for root, dirs, files in os.walk(
                project_dir,
                followlinks=False,
            ):
                root_path = Path(root)

                # Do not traverse symlinked directories.
                dirs[:] = [
                    name for name in dirs
                    if name not in excluded_dirs
                    and not (root_path / name).is_symlink()
                ]

                for filename in files:
                    source = root_path / filename

                    if source.is_symlink() or not source.is_file():
                        continue

                    if filename in excluded_files:
                        continue

                    if filename.startswith(".env."):
                        continue

                    # Prevent including the archive itself.
                    if source.resolve() == zip_path.resolve():
                        continue

                    relative = source.relative_to(project_dir)

                    archive.write(
                        source,
                        arcname=relative.as_posix(),
                    )
                    file_count += 1

        if file_count == 0:
            raise ValueError(
                "The generated project contains no files."
            )

        return zip_path

    except Exception:
        zip_path.unlink(missing_ok=True)
        raise

#editing project
def apply_project_changes(changes: dict[str, str]) -> list[str]:
    """
    Write validated edits inside the generated project only.
    Existing files are backed up in memory so a write failure
    can roll back the files already changed.
    """
    root = BASE_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)

    targets = {}

    for relative_path, content in changes.items():
        if not isinstance(relative_path, str):
            raise ValueError("Invalid path.")

        if not isinstance(content, str):
            raise ValueError("Invalid file content.")

        normalized = relative_path.replace("\\", "/")
        parts = normalized.split("/")

        if (
            not normalized
            or normalized.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
            or any(part.startswith(".") for part in parts)
            or any(
                part in {
                    "node_modules", ".git", ".venv", "venv",
                    "__pycache__", "dist", "build",
                }
                for part in parts
            )
            or parts[-1] in {
                "package-lock.json", "pnpm-lock.yaml", "yarn.lock"
            }
            or parts[-1].startswith(".env")
        ):
            raise ValueError(f"Unsafe path: {relative_path}")

        target = (root / normalized).resolve()

        if not target.is_relative_to(root):
            raise ValueError("Path escapes project directory.")

        if target.exists() and not target.is_file():
            raise ValueError("Target is not a regular file.")

        if target.is_symlink():
            raise ValueError("Symbolic links are not allowed.")

        if len(content.encode("utf-8")) > 80_000:
            raise ValueError("File exceeds the size limit.")

        targets[normalized] = (target, content)

    # Capture original contents before writing anything.
    originals = {}
    created = []

    for relative, (target, _) in targets.items():
        if target.exists():
            originals[relative] = target.read_bytes()
        else:
            originals[relative] = None

    try:
        for relative, (target, content) in targets.items():
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            # Atomic replacement avoids partially written files.
            temporary = target.with_name(
                target.name + ".edit-tmp"
            )

            try:
                temporary.write_text(
                    content,
                    encoding="utf-8",
                )
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)

            created.append(relative)

    except Exception:
        # Best-effort rollback if a write fails.
        for relative in reversed(created):
            target, _ = targets[relative]
            original = originals[relative]

            try:
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(original)
            except OSError:
                pass

        raise

    return list(targets.keys())