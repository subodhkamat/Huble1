import asyncio
import json
import os
import subprocess
from pathlib import Path

from ai_service import client, MODEL
from edit_service import read_project_files, parse_edit_response
from project_service import BASE_DIR, apply_project_changes


MAX_BUILD_LOG = 15000
BUILD_TIMEOUT_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 3

DEBUG_REPAIR_PROMPT = """
You are an autonomous React/Vite debugging engineer.

Your task is to fix the build error in the supplied project.

Rules:
1. Identify the root cause from the build output.
2. Make the smallest changes needed to fix the error.
3. Preserve existing functionality and design.
4. Return complete contents for every changed file.
5. Do not return Markdown fences.
6. Do not add unnecessary dependencies.
7. Do not modify environment files, secrets, lockfiles,
   node_modules, or build output.
8. Do not claim the build is fixed without evidence.
9. Return valid JSON in exactly this format:

{
  "changes": {
    "src/App.jsx": "complete corrected file contents"
  },
  "summary": "Brief explanation of the fix"
}

If the error cannot be fixed confidently, return an empty
changes object and explain why in summary.
"""


def run_build() -> dict:
    """
    Run npm run build in the generated project directory.

    This executes the generated project's npm build script.
    Use this local development implementation only with trusted
    project code; it is not a security sandbox.
    """
    root = Path(BASE_DIR).resolve()

    package_json = root / "package.json"

    if not package_json.is_file():
        return {
            "success": False,
            "output": (
                f"package.json was not found in the generated project: {root}"
            ),
        }

    if not (root / "node_modules").is_dir():
        return {
            "success": False,
            "output": (
                "Dependencies are not installed. Run npm install "
                "in the generated project before auto-debugging."
            ),
        }

    # Do not pass common API keys or credentials to generated build scripts.
    # This is risk reduction, not a substitute for process isolation.
    env = os.environ.copy()

    sensitive_terms = (
        "API_KEY",
        "SECRET",
        "PASSWORD",
        "ACCESS_TOKEN",
        "AUTH_TOKEN",
        "PRIVATE_KEY",
    )

    for key in list(env):
        if any(term in key.upper() for term in sensitive_terms):
            env.pop(key, None)

    try:
        if os.name == "nt":
            # Fixed command; no user input is interpolated into it.
            result = subprocess.run(
                "npm.cmd run build",
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT_SECONDS,
                env=env,
                shell=True,
                check=False,
            )
        else:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT_SECONDS,
                env=env,
                shell=False,
                check=False,
            )

        output = (
            f"Exit code: {result.returncode}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

        return {
            "success": result.returncode == 0,
            "output": output[-MAX_BUILD_LOG:],
        }

    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")

        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")

        output = (
            f"Build timed out after {BUILD_TIMEOUT_SECONDS} seconds.\n"
            f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        )

        return {
            "success": False,
            "output": output[-MAX_BUILD_LOG:],
        }

    except FileNotFoundError:
        return {
            "success": False,
            "output": (
                "npm was not found. Install Node.js and npm, "
                "then restart the backend terminal."
            ),
        }

    except OSError as exc:
        return {
            "success": False,
            "output": f"Could not run the build: {exc}",
        }


async def repair_build_error(build_error: str) -> dict:
    """
    Ask the AI to repair the project based on its build error.
    """
    files = await asyncio.to_thread(read_project_files)

    if not files:
        raise ValueError(
            "No readable project source files were found. "
            "Generate a project before running auto-debug."
        )

    project_context = json.dumps(files, ensure_ascii=False)

    response = await client.responses.create(
        model=MODEL,
        instructions=DEBUG_REPAIR_PROMPT,
        input=(
            "BUILD ERROR:\n"
            f"{build_error}\n\n"
            "CURRENT PROJECT FILES (JSON):\n"
            f"{project_context}"
        ),
    )

    output = response.output_text

    if not output:
        raise ValueError("The AI returned an empty debugging response.")

    # Reuse Phase 4's response parsing and file-path validation.
    return parse_edit_response(output)


async def auto_debug_project(max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> dict:
    """
    Build, repair, and retry up to max_attempts build runs.
    """
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be between 1 and 3.")

    root = Path(BASE_DIR).resolve()

    if not root.is_dir():
        raise FileNotFoundError(
            "Generated project not found. Generate a project first."
        )

    changed_files = []
    history = []

    for attempt in range(1, max_attempts + 1):
        # The subprocess is blocking, so run it in a worker thread.
        build_result = await asyncio.to_thread(run_build)

        history.append(
            {
                "attempt": attempt,
                "success": build_result["success"],
                "output": build_result["output"],
            }
        )

        if build_result["success"]:
            return {
                "success": True,
                "attempts": attempt,
                "summary": (
                    "Build succeeded."
                    if not changed_files
                    else "Build succeeded after AI debugging."
                ),
                "changed_files": list(dict.fromkeys(changed_files)),
                "build_output": build_result["output"],
                "history": history,
            }

        # Do not ask AI to fix the error when no further build
        # attempt is available.
        if attempt == max_attempts:
            break

        repair = await repair_build_error(build_result["output"])
        changes = repair.get("changes", {})
        summary = repair.get("summary", "AI analyzed the build error.")

        if not changes:
            history.append(
                {
                    "attempt": attempt,
                    "success": False,
                    "repair_summary": summary,
                    "repair_applied": False,
                }
            )
            break

        # This function must validate every path before writing files.
        applied = await asyncio.to_thread(apply_project_changes, changes)

        if not applied:
            history.append(
                {
                    "attempt": attempt,
                    "success": False,
                    "repair_summary": summary,
                    "repair_applied": False,
                }
            )
            break

        changed_files.extend(applied)

        history.append(
            {
                "attempt": attempt,
                "success": False,
                "repair_summary": summary,
                "repair_applied": True,
                "changed_files": applied,
            }
        )

    last_output = history[-1]["output"] if history else "No build was run."

    return {
        "success": False,
        "attempts": len(
            [item for item in history if "output" in item]
        ),
        "summary": "Auto-debug finished without a successful build.",
        "changed_files": list(dict.fromkeys(changed_files)),
        "build_output": last_output,
        "history": history,
    }