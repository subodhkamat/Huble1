
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

from fastapi import HTTPException
from fastapi.responses import Response


PROJECT_DIR = (
    Path(__file__).resolve().parent.parent
    / "workspace"
    / "generated_project"
)


def export_html():
    project_dir = PROJECT_DIR.resolve()

    # Find the React entry file.
    entry_file = project_dir / "src" / "main.jsx"
    if not entry_file.is_file():
        entry_file = project_dir / "main.jsx"

    if not entry_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Generate a project before exporting HTML.",
        )

    package_file = project_dir / "package.json"
    if not package_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Generated project package.json was not found.",
        )

    if not (project_dir / "node_modules").is_dir():
        raise HTTPException(
            status_code=500,
            detail="Dependencies are missing. Install the generated project's dependencies first.",
        )

    node = shutil.which("node")
    if not node:
        raise HTTPException(
            status_code=500,
            detail="Node.js is unavailable on the backend.",
        )

    esbuild_cli = (
        project_dir / "node_modules" / "esbuild" / "bin" / "esbuild"
    )
    if not esbuild_cli.is_file():
        raise HTTPException(
            status_code=500,
            detail="esbuild CLI was not found. Reinstall project dependencies.",
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        js_file = temp_path / "bundle.js"
        css_file = temp_path / "bundle.css"

        # Bundle JavaScript. CSS imports are handled in a separate pass.
        js_result = subprocess.run(
            [
                node,
                str(esbuild_cli),
                str(entry_file),
                "--bundle",
                "--minify",
                "--format=iife",
                "--loader:.jsx=jsx",
                "--loader:.css=empty",
                f"--outfile={js_file}",
            ],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if js_result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"JavaScript bundling failed: {js_result.stderr[-2000:]}",
            )

        # Bundle CSS imports into one CSS file.
        css_result = subprocess.run(
            [
                node,
                str(esbuild_cli),
                str(entry_file),
                "--bundle",
                "--minify",
                "--loader:.jsx=jsx",
                "--loader:.js=empty",
                "--loader:.css=css",
                f"--outfile={css_file}",
            ],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if css_result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"CSS bundling failed: {css_result.stderr[-2000:]}",
            )

        js_code = js_file.read_text(encoding="utf-8")
        css_code = (
            css_file.read_text(encoding="utf-8")
            if css_file.is_file()
            else ""
        )

        # Avoid prematurely closing the HTML script element.
        js_code = js_code.replace("</script", r"<\/script")

        # Escape a closing style tag if it appears in CSS content.
        css_code = css_code.replace("</style", r"<\/style")

        html = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BuildAI App</title>
    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
        }}
        {css_code}
    </style>
</head>
<body>
    <div id="root"></div>
    <script>{js_code}</script>
</body>
</html>
"""

        return Response(
            content=html,
            media_type="text/html",
            headers={
                "Content-Disposition": 'attachment; filename="buildai-app.html"'
            },
        )
