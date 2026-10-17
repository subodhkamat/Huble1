
from pathlib import Path
import subprocess
import tempfile

from fastapi import HTTPException
from fastapi.responses import FileResponse


PROJECT_DIR = (
    Path(__file__).resolve().parent.parent
    / "workspace"
    / "generated_project"
)


def export_html():
    project_dir = PROJECT_DIR.resolve()

    entry_file = project_dir / "src" / "main.jsx"

    if not entry_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Generate a React project before exporting HTML.",
        )

    # A standalone HTML export needs an installed bundler.
    esbuild = (
        project_dir.parent.parent
        / "frontend"
        / "node_modules"
        / ".bin"
        / "esbuild"
    )

    if not esbuild.exists():
        raise HTTPException(
            status_code=500,
            detail="esbuild is not installed at the expected path.",
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        js_file = temp_path / "bundle.js"

        result = subprocess.run(
            [
                str(esbuild),
                str(entry_file),
                "--bundle",
                "--minify",
                "--loader:.jsx=jsx",
                "--loader:.css=css",
                f"--outfile={js_file}",
            ],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"HTML bundling failed: {result.stderr[-1500:]}",
            )

        js_code = js_file.read_text(encoding="utf-8")

        # Prevent an embedded script from prematurely closing its tag.
        js_code = js_code.replace("</script", r"<\/script")

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BuildAI App</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; }}
  </style>
</head>
<body>
  <div id="root"></div>
  <script>{js_code}</script>
</body>
</html>
"""

        output_file = temp_path / "index.html"
        output_file.write_text(html, encoding="utf-8")

        # Return a response while the temporary directory still exists.
        # FileResponse streams later, so don't use it with this temp file.
        from fastapi.responses import Response

        return Response(
            content=html,
            media_type="text/html",
            headers={
                "Content-Disposition": 'attachment; filename="buildai-app.html"'
            },
        )
