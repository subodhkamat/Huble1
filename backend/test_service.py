
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from project_service import BASE_DIR


PROJECT_DIR = Path(BASE_DIR).resolve()
MAX_LOG_LENGTH = 12000


def run_build() -> dict:
    """Run the generated project's production build."""

    package_json = PROJECT_DIR / "package.json"

    if not package_json.is_file():
        return {
            "status": "failed",
            "message": "package.json was not found.",
            "output": "",
        }

    if not (PROJECT_DIR / "node_modules").is_dir():
        return {
            "status": "failed",
            "message": "Dependencies are missing. Run npm install first.",
            "output": "",
        }

    if os.name == "nt":
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            return {
                "status": "failed",
                "message": "npm was not found. Install Node.js.",
                "output": "",
            }
        command = [npm, "run", "build"]
    else:
        npm = shutil.which("npm")
        if not npm:
            return {
                "status": "failed",
                "message": "npm was not found. Install Node.js.",
                "output": "",
            }
        command = [npm, "run", "build"]

    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
            shell=False,
        )

        output = (
            (result.stdout or "")
            + "\n"
            + (result.stderr or "")
        )[-MAX_LOG_LENGTH:]

        passed = result.returncode == 0

        return {
            "status": "passed" if passed else "failed",
            "message": (
                "Production build succeeded."
                if passed
                else "Production build failed."
            ),
            "output": output,
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "message": "Build timed out after 120 seconds.",
            "output": "",
        }

    except OSError as exc:
        return {
            "status": "failed",
            "message": f"Could not start the build: {exc}",
            "output": "",
        }


def run_structure_checks() -> list[dict]:
    """Check essential generated-project files."""

    checks = []

    required_files = [
        "package.json",
        "index.html",
    ]

    entry_candidates = [
        "src/main.jsx",
        "src/main.tsx",
        "src/main.js",
        "src/main.ts",
    ]

    for relative_path in required_files:
        exists = (PROJECT_DIR / relative_path).is_file()
        checks.append({
            "name": f"Required file: {relative_path}",
            "status": "passed" if exists else "failed",
            "message": (
                "File exists."
                if exists
                else "Required file is missing."
            ),
        })

    has_entry = any(
        (PROJECT_DIR / path).is_file()
        for path in entry_candidates
    )

    checks.append({
        "name": "Application entry point",
        "status": "passed" if has_entry else "failed",
        "message": (
            "An application entry point exists."
            if has_entry
            else "No supported src/main entry file was found."
        ),
    })

    package_path = PROJECT_DIR / "package.json"

    try:
        package = json.loads(
            package_path.read_text(encoding="utf-8")
        )
        has_build_script = (
            isinstance(package.get("scripts"), dict)
            and bool(package["scripts"].get("build"))
        )

        checks.append({
            "name": "Build script",
            "status": "passed" if has_build_script else "failed",
            "message": (
                "A build script is configured."
                if has_build_script
                else "package.json has no scripts.build entry."
            ),
        })

    except (OSError, json.JSONDecodeError) as exc:
        checks.append({
            "name": "Valid package.json",
            "status": "failed",
            "message": str(exc),
        })

    return checks


async def run_browser_smoke_test(
    preview_url: str,
) -> dict:
    """Open a running preview and capture browser errors."""

    parsed = urlparse(preview_url)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return {
            "status": "failed",
            "message": "A valid HTTP(S) preview URL is required.",
            "errors": [],
        }

    # Prevent this endpoint from being used to probe arbitrary hosts.
    allowed_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.hostname not in allowed_hosts:
        return {
            "status": "failed",
            "message": "Browser testing is limited to local preview hosts.",
            "errors": [],
        }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "status": "skipped",
            "message": (
                "Playwright is not installed in this environment."
            ),
            "errors": [],
        }

    errors = []

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True
            )

            try:
                page = await browser.new_page()

                page.on(
                    "pageerror",
                    lambda error: errors.append(
                        f"JavaScript exception: {error}"
                    ),
                )

                page.on(
                    "console",
                    lambda message: errors.append(
                        f"Console error: {message.text}"
                    ) if message.type == "error" else None,
                )

                response = await page.goto(
                    preview_url,
                    wait_until="domcontentloaded",
                    timeout=20000,
                )

                if response is None:
                    return {
                        "status": "failed",
                        "message": "The preview returned no HTTP response.",
                        "errors": errors,
                    }

                if response.status >= 400:
                    errors.append(
                        f"Preview returned HTTP {response.status}."
                    )

                await page.wait_for_timeout(1500)

                title = await page.title()
                body_text = await page.locator("body").inner_text(
                    timeout=5000
                )

                if not body_text.strip():
                    errors.append("The page body is empty.")

                return {
                    "status": "failed" if errors else "passed",
                    "message": (
                        "Browser smoke test completed."
                        if not errors
                        else "Browser errors were detected."
                    ),
                    "http_status": response.status,
                    "page_title": title,
                    "errors": errors[:50],
                }

            finally:
                await browser.close()

    except Exception as exc:
        return {
            "status": "failed",
            "message": f"Browser test could not complete: {exc}",
            "errors": errors[:50],
        }


async def run_autonomous_tests(
    preview_url: str | None = None,
    run_browser: bool = True,
) -> dict:
    """Run structural, production-build, and optional browser checks."""

    structure_checks = run_structure_checks()
    build_result = await asyncio.to_thread(run_build)

    results = [
        *structure_checks,
        {
            "name": "Production build",
            "status": build_result["status"],
            "message": build_result["message"],
            "output": build_result.get("output", ""),
        },
    ]

    browser_result = None

    if run_browser:
        if preview_url:
            browser_result = await run_browser_smoke_test(
                preview_url
            )
        else:
            browser_result = {
                "status": "skipped",
                "message": (
                    "Start the live preview and supply preview_url "
                    "to run browser tests."
                ),
                "errors": [],
            }

        results.append({
            "name": "Browser smoke test",
            "status": browser_result["status"],
            "message": browser_result["message"],
            "errors": browser_result.get("errors", []),
        })

    passed = sum(
        item["status"] == "passed" for item in results
    )
    failed = sum(
        item["status"] == "failed" for item in results
    )
    skipped = sum(
        item["status"] == "skipped" for item in results
    )

    return {
        "success": failed == 0,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "tests": results,
        "build_output": build_result.get("output", ""),
        "browser": browser_result,
        "message": (
            "All executed checks passed."
            if failed == 0 and skipped == 0
            else (
                "Some checks were skipped."
                if failed == 0
                else "One or more checks failed."
            )
        ),
    }


