import asyncio
import os
from pathlib import Path

import httpx
import websockets
from dotenv import load_dotenv

# Load environment variables before importing modules that read them.
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask
from starlette.middleware.sessions import SessionMiddleware

from debug_service import auto_debug_project
from edit_service import edit_project
from html_export import export_html
from model_config import generate_project1
from oauth_service import router as oauth_router
from preview_service import start_preview
from project_planner import analyze_project, plan_project_change
from project_service import apply_project_changes, create_project_zip, save_project
from schemas import (
    AutoDebugRequest,
    EditRequest,
    GenerateRequest,
    GenerateResponse,
    ProjectPlanRequest,
    RuntimeErrorReport,
    TestProjectRequest,
)
from terminal_service import (
    get_terminal_status,
    install_dependencies,
    start_dev_server,
    stop_dev_server,
)
from test_service import run_autonomous_tests

# Keep paths explicit for the deployed backend layout.
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent / "workspace" / "generated_project"

oauth_state_secret = os.getenv("OAUTH_STATE_SECRET")
if not oauth_state_secret:
    raise RuntimeError("OAUTH_STATE_SECRET is missing from the environment")

cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"

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


@app.post("/preview")
async def preview():
    try:
        start_preview()

        # Browser must use the public FastAPI proxy, not
        # the internal 127.0.0.1:5173 address.
        return {
            "success": True,
            "preview_url": "/preview/",
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
            detail=f"Could not start the project preview: {exc}",
        ) from exc


@app.api_route("/preview", methods=["GET", "HEAD"])
@app.api_route("/preview/{path:path}", methods=["GET", "HEAD"])
async def preview_proxy(request: Request, path: str = ""):
    from preview_service import PREVIEW_URL

    target_url = f"{PREVIEW_URL.rstrip('/')}/{path.lstrip('/')}"

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            upstream = await client.request(
                request.method,
                target_url,
                params=request.query_params,
                headers={
                    key: value
                    for key, value in request.headers.items()
                    if key.lower() in {
                        "accept",
                        "range",
                        "if-none-match",
                        "if-modified-since",
                    }
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


@app.websocket("/preview")
@app.websocket("/preview/")
async def preview_websocket(websocket: WebSocket):
    """Forward Vite's HMR WebSocket through the public /preview/ route.

    The external /preview/ prefix is stripped by this proxy, so the internal
    Vite connection normally uses /. Keep the query string because Vite may
    include its WebSocket token there.
    """
    from preview_service import PREVIEW_PORT

    query = websocket.url.query
    target_url = f"ws://127.0.0.1:{PREVIEW_PORT}/"
    if query:
        target_url = f"{target_url}?{query}"

    try:
        # Connect upstream before accepting the browser handshake. If Vite is
        # unavailable, the log will show the upstream failure rather than
        # accepting a WebSocket that cannot be proxied.
        async with websockets.connect(
            target_url,
            open_timeout=10,
            ping_interval=20,
            close_timeout=5,
            max_size=8 * 1024 * 1024,
        ) as upstream:
            await websocket.accept()

            async def browser_to_vite():
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if message.get("text") is not None:
                        await upstream.send(message["text"])
                    elif message.get("bytes") is not None:
                        await upstream.send(message["bytes"])

            async def vite_to_browser():
                while True:
                    message = await upstream.recv()
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = {
                asyncio.create_task(browser_to_vite(), name="browser-to-vite"),
                asyncio.create_task(vite_to_browser(), name="vite-to-browser"),
            }

            try:
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    if not task.cancelled():
                        error = task.exception()
                        if error is not None and not isinstance(
                            error, WebSocketDisconnect
                        ):
                            print(f"Preview WebSocket forwarding error: {error!r}")

                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(
            "Preview WebSocket proxy failed "
            f"(upstream={target_url!r}): {type(exc).__name__}: {exc}"
        )
        # If the browser handshake has not been accepted, Starlette will reject
        # it. Otherwise close with a server-error code.
        try:
            if websocket.application_state.name == "CONNECTED":
                await websocket.close(code=1011, reason="Preview WebSocket failed")
            else:
                await websocket.close()
        except Exception:
            pass
