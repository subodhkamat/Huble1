
import json
import re
from pathlib import Path

from ai_service import client, MODEL
from project_service import BASE_DIR


MAX_FILE_SIZE = 80_000
MAX_TOTAL_CONTEXT = 180_000

EDIT_PROMPT = """
You are an expert software engineer working inside an
AI application builder.

The user wants to modify an EXISTING React + Vite project.

You will receive:
1. The user's requested change.
2. The current project files.

Rules:
- Preserve existing functionality unless the user asks to change it.
- Return only files that need to be created or modified.
- Read the existing code before deciding what to change.
- Keep the existing framework and architecture.
- Use complete file contents, not partial snippets or diffs.
- Do not return markdown fences.
- Do not modify .env files, secrets, node_modules or lockfiles.
- Do not add unrelated files or dependencies.
- Do not delete files.
- Do not claim features work unless implemented.
- Keep code responsive and accessible.

Return exactly this JSON structure:
{
  "changes": {
    "src/App.jsx": "complete updated file contents",
    "src/App.css": "complete updated file contents"
  },
  "summary": "Brief explanation of the changes"
}

If no files need to change, return an empty changes object
and explain why in the summary.
"""


def read_project_files() -> dict[str, str]:
    root = Path(BASE_DIR).resolve()

    if not root.is_dir():
        raise FileNotFoundError(
            "No generated project found. Generate a project first."
        )

    ignored_dirs = {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
    }

    ignored_files = {
        ".env",
        ".env.local",
        ".env.development.local",
        ".env.production.local",
        ".env.test.local",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
    }

    result = {}
    total_size = 0

    for current, dirs, filenames in __import__("os").walk(
        root,
        followlinks=False,
    ):
        current_path = Path(current)

        dirs[:] = [
            name for name in dirs
            if name not in ignored_dirs
            and not (current_path / name).is_symlink()
        ]

        for filename in filenames:
            path = current_path / filename

            if path.is_symlink() or not path.is_file():
                continue

            if filename in ignored_files or filename.startswith(".env."):
                continue

            if path.suffix.lower() not in {
                ".jsx", ".js", ".tsx", ".ts",
                ".css", ".html", ".json",
                ".svg", ".md",
            }:
                continue

            size = path.stat().st_size

            if size > MAX_FILE_SIZE:
                continue

            total_size += size

            if total_size > MAX_TOTAL_CONTEXT:
                raise ValueError(
                    "Project is too large for one edit request. "
                    "Use relevant-file retrieval or chunked context."
                )

            relative = path.relative_to(root).as_posix()

            result[relative] = path.read_text(
                encoding="utf-8"
            )

    if not result:
        raise ValueError("No readable project files found.")

    return result



def parse_edit_response(output: str) -> dict:
    if not isinstance(output, str) or not output.strip():
        raise ValueError("AI returned an empty debugging response.")

    output = output.strip()

    # Remove an optional Markdown JSON code fence.
    output = re.sub(
        r"^```(?:json)?[ \t]*\r?\n?",
        "",
        output,
        count=1,
        flags=re.IGNORECASE,
    )
    output = re.sub(r"\r?\n?```[ \t]*$", "", output, count=1)
    output = output.strip()

    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"AI returned invalid JSON: {exc.msg} at line "
            f"{exc.lineno}, column {exc.colno}."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("AI response must be a JSON object.")

    changes = data.get("changes")
    summary = data.get("summary")
    verification = data.get("verification")

    if not isinstance(changes, dict):
        raise ValueError("AI returned invalid changes.")

    if not isinstance(summary, str):
        raise ValueError("AI returned an invalid summary.")

    # Validate optional verification details without trusting AI claims
    # as proof that a build or runtime test actually passed.
    if verification is not None:
        if not isinstance(verification, dict):
            raise ValueError("AI returned invalid verification details.")

        allowed_statuses = {"passed", "failed", "not_run"}

        for check in ("build", "runtime"):
            status = verification.get(check)
            if status is not None and status not in allowed_statuses:
                raise ValueError(
                    f"AI returned an invalid verification status: {check}."
                )

        checks = verification.get("checks", [])
        if not isinstance(checks, list):
            raise ValueError("AI verification checks must be a list.")

        for check in checks:
            if not isinstance(check, dict):
                raise ValueError("AI returned an invalid verification check.")

            if not isinstance(check.get("name"), str):
                raise ValueError("Verification check name must be a string.")

            if check.get("status") not in allowed_statuses:
                raise ValueError("AI returned an invalid check status.")

            if not isinstance(check.get("details"), str):
                raise ValueError("Verification check details must be a string.")

    for path, content in changes.items():
        if not isinstance(path, str) or not isinstance(content, str):
            raise ValueError("Invalid file path or content.")

        normalized = path.replace("\\", "/")
        parts = normalized.split("/")

        blocked_names = {
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "dist",
            "build",
        }

        if (
            not normalized
            or normalized.startswith("/")
            or re.match(r"^[a-zA-Z]:", normalized)
            or any(part in {"", ".", ".."} for part in parts)
            or any(part.startswith(".") for part in parts)
            or any(part.lower() in blocked_names for part in parts)
            or parts[-1].lower() in {
                "package-lock.json",
                "pnpm-lock.yaml",
                "yarn.lock",
            }
            or parts[-1].lower().startswith(".env")
        ):
            raise ValueError(f"Unsafe file path: {path}")

        if len(content.encode("utf-8")) > MAX_FILE_SIZE:
            raise ValueError(f"File is too large: {path}")

    return {
        "changes": changes,
        "summary": summary,
        "verification": verification or {},
    }



async def edit_project(prompt: str) -> dict:
    files = read_project_files()

    context = json.dumps(
        files,
        ensure_ascii=False,
    )

    response = await client.responses.create(
        model=MODEL,
        instructions=EDIT_PROMPT,
        input=(
            f"USER REQUEST:\n{prompt}\n\n"
            f"CURRENT PROJECT FILES:\n{context}"
        ),
    )

    if not response.output_text:
        raise ValueError("AI returned an empty editing response.")

    return parse_edit_response(response.output_text)