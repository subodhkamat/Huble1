from fastapi import Request
from fastapi.responses import Response
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from preview_service import start_preview
from schemas import GenerateRequest, GenerateResponse
from ai_service import generate_project
from project_service import save_project
import os
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from project_service import create_project_zip
from schemas import EditRequest
from edit_service import edit_project
from project_service import apply_project_changes
from schemas import AutoDebugRequest
from debug_service import auto_debug_project
from schemas import RuntimeErrorReport
from test_service import run_autonomous_tests
from schemas import TestProjectRequest
from schemas import ProjectPlanRequest
from starlette.middleware.sessions import SessionMiddleware
from model_config import generate_project1
from database import BASE_DIR
from oauth_service import router as oauth_router
from project_planner import analyze_project, plan_project_change
from terminal_service import (
    get_terminal_status,
    install_dependencies,
    start_dev_server,
    stop_dev_server,
)
import httpx
import subprocess
from html_export import export_html

BASE_DIR = Path(__file__).resolve().parent

PROJECT_DIR = BASE_DIR.parent / "workspace" / "generated_project"

ESBUILD = PROJECT_DIR / "node_modules" / ".bin" / "esbuild"

print("ESBUILD PATH:", ESBUILD)
print("ESBUILD EXISTS:", ESBUILD.exists())
print("ESBUILD IS SYMLINK:", ESBUILD.is_symlink())

print("ESBUILD MODE:", oct(ESBUILD.stat().st_mode))
print("EXECUTABLE:", os.access(ESBUILD, os.X_OK))
print("ESBUILD FILE:", ESBUILD.is_file())

try:
    result = subprocess.run(
    ["npm", "install", "--include=dev"],
    cwd=str(PROJECT_DIR),
    capture_output=True,
    text=True,
    timeout=180,
)
    print("ESBUILD RETURN CODE:", result.returncode)
    print("ESBUILD STDOUT:", result.stdout)
    print("ESBUILD STDERR:", result.stderr)


    if result.returncode != 0:
       raise RuntimeError(f"npm install failed: {result.stderr[-2000:]}")
except Exception as error:
    print("ESBUILD EXECUTION ERROR:", repr(error))

oauth_state_secret = os.getenv("OAUTH_STATE_SECRET")

from config import FRONTEND_URL as frontend_url

if not oauth_state_secret:
    raise RuntimeError(
        "OAUTH_STATE_SECRET is missing from backend/.env"
    )

cookie_secure = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)

import asyncio

app = FastAPI(
    title="AI App Builder",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://huble1.vercel.app",
                    "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-CSRF-Token",
    ],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=oauth_state_secret,
    same_site="lax",
    https_only=cookie_secure,
    max_age=600,
)

app.include_router(oauth_router)


@app.get("/")
async def home():
    return {
        "service": "AI App Builder",
        "status": "running"
    }


@app.post(
    "/generate",
    response_model=GenerateResponse
)
async def generate(request: GenerateRequest):
    try:
        print("1")
        files = await generate_project1(request.prompt)
        print("1cc")
        save_project(files)
        print("2")
        return GenerateResponse(
            success=True,
            message="Project generated and saved.",
            files=files
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Invalid AI output: {exc}"
        ) from exc

    except Exception as exc:
        # Do not expose API keys or internal stack
        # traces to the browser.
        print(f"Generation failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Project generation failed."
        ) from exc


@app.api_route(
    "/preview",
    methods=["GET", "HEAD"],
)
async def preview_home(request: Request):
    return await preview_proxy("", request)

@app.post("/preview")
async def preview():
    try:
        url = start_preview()

        return {
            "success": True,
            "preview_url": url,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print(f"Preview failed: {exc}")

        raise HTTPException(
            status_code=500,
            detail="Could not start the project preview.",
        ) from exc


@app.api_route(
    "/preview/{path:path}",
    methods=["GET", "HEAD"],
)
async def preview_proxy(path: str, request: Request):
    import httpx

    from preview_service import PREVIEW_URL

    target_url = f"{PREVIEW_URL}/{path}"

    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=30.0,
        ) as client:
            upstream = await client.request(
                request.method,
                target_url,
                params=request.query_params,
                headers={
                    key: value
                    for key, value in request.headers.items()
                    if key.lower() in {"accept", "range", "if-none-match"}
                },
            )

        excluded_headers = {
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection",
        }

        headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in excluded_headers
        }

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=headers,
            media_type=upstream.headers.get("content-type"),
        )

    except httpx.HTTPError as exc:
        print(f"Preview proxy failed: {exc}")
        raise HTTPException(
            status_code=502,
            detail="Could not connect to the running preview.",
        ) from exc


@app.get("/download")
def download_project():
    zip_path = None

    try:
        zip_path = create_project_zip()

        return FileResponse(
            path=str(zip_path),
            media_type="application/zip",
            filename="generated_project.zip",
            background=BackgroundTask(
                lambda: Path(zip_path).unlink(missing_ok=True)
            ),
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        if zip_path is not None:
            Path(zip_path).unlink(missing_ok=True)

        print(f"Project download failed: {exc}")

        raise HTTPException(
            status_code=500,
            detail="Could not create project ZIP.",
        ) from exc


@app.post("/edit")
async def edit_existing_project(request: EditRequest):
    try:
        result = await edit_project(request.prompt)

        changes = result["changes"]

        if not changes:
            return {
                "success": True,
                "summary": result["summary"],
                "changed_files": [],
                "files": {},
            }

        changed_files = apply_project_changes(changes)

        return {
            "success": True,
            "summary": result["summary"],
            "changed_files": changed_files,
            "files": changes,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Generate a project before editing.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print(f"Project editing failed: {exc}")

        raise HTTPException(
            status_code=500,
            detail="Could not edit the project.",
        ) from exc


@app.post("/auto-debug")
async def run_auto_debug(request: AutoDebugRequest):
    try:
        result = await auto_debug_project(
            max_attempts=request.max_attempts
        )
        return result

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print(f"Auto-debug failed: {exc}")

        raise HTTPException(
            status_code=500,
            detail="Auto-debug failed. Check the backend terminal.",
        ) from exc


@app.post("/runtime-error")
async def receive_runtime_error(report: RuntimeErrorReport):
    # Keep logs bounded and avoid dumping unlimited browser data.
    print("\n=== BuildAI Runtime Error ===")
    print(f"Type: {report.type}")
    print(f"Message: {report.message}")
    print(f"Source: {report.filename}")
    print(f"Location: {report.line}:{report.column}")

    if report.stack:
        print(f"Stack:\n{report.stack[:8000]}")

    print("=============================\n")

    return {
        "success": True,
        "message": "Runtime error received.",
    }

@app.post("/test-project")
async def test_project(request: TestProjectRequest):
    return await run_autonomous_tests(
        preview_url=request.preview_url,
        run_browser=request.run_browser,
    )


@app.get("/analyze-project")
async def analyze_existing_project():
    try:
        return await analyze_project()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/plan-project")
async def create_project_plan(request: ProjectPlanRequest):
    try:
        return await plan_project_change(request.prompt)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))



@app.get("/terminal/status")
async def terminal_status():
    return get_terminal_status()


@app.post("/terminal/install")
async def terminal_install():
    try:
        return await asyncio.to_thread(install_dependencies)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/terminal/start")
async def terminal_start():
    try:
        return await asyncio.to_thread(start_dev_server)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/terminal/stop")
async def terminal_stop():
    try:
        return await asyncio.to_thread(stop_dev_server)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/download-html")
async def download_html():
    return export_html()