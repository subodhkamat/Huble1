
from pathlib import Path
import os
import zipfile
import re
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
    Safely apply AI-generated file changes inside the generated project.

    Validates all paths and contents before writing. Uses temporary files
    for atomic replacement and attempts to restore original files if a
    write operation fails.
    """
    if not isinstance(changes, dict):
        raise ValueError("Changes must be a dictionary.")

    if not changes:
        return []

    root = BASE_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)

    max_file_size = 80_000

    blocked_directories = {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
    }

    blocked_lockfiles = {
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
    }

    targets = {}

    # Validate EVERY proposed change before writing any files.
    for relative_path, content in changes.items():
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("Invalid file path.")

        if not isinstance(content, str):
            raise ValueError(
                f"Invalid file content: {relative_path}"
            )

        normalized = relative_path.replace("\\", "/")
        parts = normalized.split("/")

        if (
            normalized.startswith("/")
            or re.match(r"^[a-zA-Z]:", normalized)
            or any(part in {"", ".", ".."} for part in parts)
            or any(part.startswith(".") for part in parts)
            or any(
                part.lower() in blocked_directories
                for part in parts
            )
            or parts[-1].lower() in blocked_lockfiles
            or parts[-1].lower().startswith(".env")
        ):
            raise ValueError(f"Unsafe file path: {relative_path}")

        if len(content.encode("utf-8")) > max_file_size:
            raise ValueError(
                f"File exceeds the size limit: {relative_path}"
            )

        # Inspect the original path components BEFORE resolving.
        candidate = root / normalized
        current = root

        for part in parts:
            current = current / part

            if current.is_symlink():
                raise ValueError(
                    f"Symbolic links are not allowed: {relative_path}"
                )

        target = candidate.resolve()

        if not target.is_relative_to(root):
            raise ValueError(
                f"Path escapes project directory: {relative_path}"
            )

        if target.exists() and not target.is_file():
            raise ValueError(
                f"Target is not a regular file: {relative_path}"
            )

        # Avoid two different input paths targeting the same file.
        if target in (entry[0] for entry in targets.values()):
            raise ValueError(
                f"Duplicate target path: {relative_path}"
            )

        targets[normalized] = (target, content)

    # Back up original contents before writing.
    originals = {}

    for relative, (target, _) in targets.items():
        if target.exists():
            originals[relative] = target.read_bytes()
        else:
            originals[relative] = None

    created = []
    touched = []

    try:
        for relative, (target, content) in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)

            # Recheck the destination immediately before writing.
            # This also detects a symlink introduced after validation.
            current = root

            for part in relative.split("/"):
                current = current / part

                if current.is_symlink():
                    raise ValueError(
                        f"Symbolic link detected before writing: {relative}"
                    )

            if not target.is_relative_to(root):
                raise ValueError(
                    f"Path escapes project directory: {relative}"
                )

            if target.exists() and not target.is_file():
                raise ValueError(
                    f"Target is not a regular file: {relative}"
                )

            temporary = target.with_name(
                target.name + ".edit-tmp"
            )

            touched.append(relative)

            try:
                temporary.write_text(
                    content,
                    encoding="utf-8",
                )
                temporary.replace(target)

                if originals[relative] is None:
                    created.append(relative)

            finally:
                temporary.unlink(missing_ok=True)

    except Exception as original_error:
        rollback_errors = []

        # Restore files in reverse order.
        for relative in reversed(touched):
            target, _ = targets[relative]
            original = originals[relative]

            try:
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    # Restore using a temporary file and atomic replace.
                    restore_temp = target.with_name(
                        target.name + ".rollback-tmp"
                    )

                    try:
                        restore_temp.write_bytes(original)
                        restore_temp.replace(target)
                    finally:
                        restore_temp.unlink(missing_ok=True)

            except OSError as rollback_error:
                rollback_errors.append(
                    f"{relative}: {rollback_error}"
                )

        if rollback_errors:
            raise RuntimeError(
                "File update failed and rollback was incomplete. "
                f"Original error: {original_error}. "
                f"Rollback errors: {'; '.join(rollback_errors)}"
            ) from original_error

        raise

    return list(targets.keys())
