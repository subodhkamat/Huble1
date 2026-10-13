
import json
import os
import re

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is missing from backend/.env")

client = AsyncOpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
    )

MODEL = os.getenv("AI_MODEL","openai/gpt-oss-20b")


SYSTEM_PROMPT = """
You are a senior full-stack software engineer
inside an AI application builder.

Generate a complete, runnable React + Vite project
based on the user's requirements.

Rules:
1. Return ONLY a valid JSON object.
2. Use a "files" object mapping relative file paths
   to their complete text contents.
3. Include package.json, index.html,
   src/main.jsx, src/App.jsx and src/App.css.
4. Create reusable components when appropriate.
5. Make the UI modern, responsive and accessible.
6. Use working interactions, not decorative buttons.
7. Use local state for frontend-only functionality.
8. Do not include markdown fences around the JSON.
9. Do not generate environment secrets.
10. Do not use absolute paths or paths containing "..".
11. Keep dependencies reasonable and specify them in
    package.json.
12. Do not claim backend features work if you have
    implemented only a frontend mockup.

Expected JSON format:
{
  "files": {
    "package.json": "...",
    "index.html": "...",
    "src/main.jsx": "...",
    "src/App.jsx": "...",
    "src/App.css": "..."
  }
}
"""


def parse_generated_json(output: str) -> dict:
    # Remove optional markdown fences if the model
    # accidentally includes them.
    output = output.strip()
    print("3b")
    output = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        output
    )
    print("4b")
    data = json.loads(output)
    files = data.get("files")
   
    print("5b")
    if not isinstance(files, dict) or not files:
        raise ValueError("AI returned no project files.")

    print("6b")
    for path, content in files.items():
        if not isinstance(path, str):
            raise ValueError("Invalid file path.")
        if not isinstance(content, str):
            raise ValueError("Invalid file content.")
        print("5b")
        normalized = path.replace("\\", "/")
        if (
            normalized.startswith("/")
            or re.match(r"^[a-zA-Z]:", normalized)
            or ".." in normalized.split("/")
        ):
            raise ValueError(f"Unsafe path: {path}")
        print("5b")
    required = {
        "package.json",
        "index.html",
        "src/main.jsx",
        "src/App.jsx",
        "src/App.css",
    }
    print("5b")
    if not required.issubset(files.keys()):
        raise ValueError("The generated project is incomplete.")

    return files



async def generate_project(prompt: str) -> dict[str, str]:
    print("1a: Starting generation")

    response = await client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
        max_output_tokens=20000
    )

    print("2a: Response received")
    print("Status:", response.status)
    print("Error:", response.error)
    print("Incomplete details:", response.incomplete_details)
    

    output = response.output_text

  

    if not output or not output.strip():
        raise ValueError(
            f"AI returned empty output. "
            f"Status={response.status}, "
            f"Error={response.error}, "
            f"Incomplete={response.incomplete_details}"
        )

    data = parse_generated_json(output)

    print("4a: JSON parsed successfully")

    return data

