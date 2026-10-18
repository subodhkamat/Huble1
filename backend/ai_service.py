
import os
from types import SimpleNamespace
import re
from dotenv import load_dotenv
from openai import AsyncOpenAI
import json
load_dotenv()

# Three configurable AI providers
PROVIDERS = [
    {
        "name": "groq",
        "api_key": os.getenv("GROQ_API_KEY"),
        "base_url": "https://api.groq.com/openai/v1",
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
    },
    {
        "name": "groq1",
        "api_key": os.getenv("GROQ1_API_KEY"),
        "base_url": "https://api.groq.com/openai/v1",
        "model": os.getenv("GROQ1_MODEL", "openai/gpt-oss-20b"),
    },
    {
        "name": "openrouter",
        "api_key": os.getenv("OPENROUTER_API_KEY"),
        "base_url": "https://openrouter.ai/api/v1",
        "model": os.getenv(
            "OPENROUTER_MODEL",
            "openai/gpt-oss-20b:free",
        ),
    },
]

ACTIVE_PROVIDERS = [
    {
        **provider,
        "client": AsyncOpenAI(
            api_key=provider["api_key"],
            base_url=provider["base_url"],
            timeout=90.0,
            max_retries=0,
        ),
    }
    for provider in PROVIDERS
    if provider["api_key"]
]

if not ACTIVE_PROVIDERS:
    raise RuntimeError(
        "No AI provider configured. Add GROQ_API_KEY, "
        "GROQ1_API_KEY, or OPENROUTER_API_KEY to backend/.env"
    )


class FallbackResponses:
    """Responses-style interface with sequential provider fallback."""

    async def create(self, **kwargs):
        instructions = kwargs.get("instructions", "")
        prompt = kwargs.get("input", "")
        max_output_tokens = kwargs.get("max_output_tokens", 8192)

        messages = []

        if instructions:
            messages.append({
                "role": "system",
                "content": instructions,
            })

        if isinstance(prompt, str):
            messages.append({
                "role": "user",
                "content": prompt,
            })
        else:
            messages.append({
                "role": "user",
                "content": str(prompt),
            })

        errors = []

        for provider in ACTIVE_PROVIDERS:
            try:
                response = (
                    await provider["client"].chat.completions.create(
                        model=provider["model"],
                        messages=messages,
                        max_tokens=max_output_tokens,
                    )
                )

                content = response.choices[0].message.content

                if not content or not content.strip():
                    raise RuntimeError("Empty response from provider")

                finish_reason = response.choices[0].finish_reason

                if finish_reason == "length":
                    raise RuntimeError(
                        "Response was truncated by the token limit"
                    )

                print(f"BuildAI AI provider: {provider['name']}")

                # Adapt the Chat Completions response to the
                # Responses-style output_text used by BuildAI.
                return SimpleNamespace(
                    output_text=content,
                    status="completed",
                    incomplete_details=None,
                )

            except Exception as exc:
                errors.append(
                    f"{provider['name']}: "
                    f"{type(exc).__name__}: {exc}"
                )
                print(f"AI fallback: {errors[-1]}")

        raise RuntimeError(
            "All configured AI providers failed. "
            + " | ".join(errors)
        )


class FallbackClient:
    def __init__(self):
        self.responses = FallbackResponses()


# Keep the existing client.responses.create(...) call unchanged.
client = FallbackClient()

# Retained for compatibility with existing code that uses MODEL.
MODEL = os.getenv("AI_MODEL", "openai/gpt-oss-20b")



SYSTEM_PROMPT = """
You are a senior full-stack engineer inside an AI app builder.
Generate a complete, runnable React + Vite project for the
user's request.

OUTPUT FORMAT
- Return ONLY one valid JSON object, no markdown fences, no text outside it.
- Shape: {"plan": "...", "files": {"path": "full file contents"}}
- Write "plan" first: 3-6 sentences covering the features, the npm
  libraries you will use, and the file structure.
- Every file must be complete. Never use placeholders such as
  "// rest of code", "...", or "TODO".
- Escape all quotes and newlines correctly so the JSON parses.

REQUIRED FILES
package.json, vite.config.js, index.html, src/main.jsx,
src/App.jsx, src/App.css, plus any components in src/components/.

DEPENDENCIES (critical)
- Allowed packages ONLY: react, react-dom, vite, @vitejs/plugin-react,
  lucide-react, jsbarcode, clsx.
- Do not import anything outside this list.
- Every package you import MUST appear in package.json "dependencies".
  Before answering, list all imports in your files and confirm each
  one is in package.json.
- If you can avoid a library (e.g. use emoji or inline SVG for icons),
  do so.

QUALITY
- Every button and input must do something real.
- Handle empty input, invalid input and errors with visible,
  friendly messages. Never let the app crash.
- Responsive layout, labelled inputs, good contrast, keyboard usable.
- Use local state for frontend-only features. Do not pretend a
  backend exists. No API keys or secrets.
- No absolute paths or ".." in file paths.

BEFORE YOU ANSWER, CHECK
1. Every imported file and package exists.
2. main.jsx mounts App into the element id used in index.html.
3. The JSON is valid.
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

    errors = []

    for provider in ACTIVE_PROVIDERS:
        print(f"Trying AI provider: {provider['name']}")

        try:
            response = await provider["client"].chat.completions.create(
                model=provider["model"],
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=20000,
            )

            print("2a: Response received")

            choice = response.choices[0]
            output = choice.message.content

            print("Status:", choice.finish_reason)
            print("Provider:", provider["name"])

            if choice.finish_reason == "length":
                raise ValueError(
                    "AI output was truncated. Try a larger token limit "
                    "if supported by the selected model."
                )

            if not output or not output.strip():
                raise ValueError("AI returned empty output.")

            # Preserve your existing JSON and project validation.
            files = parse_generated_json(output)

            print("4a: JSON parsed successfully")
            print(f"Generation succeeded using {provider['name']}")

            return files

        except Exception as exc:
            error = (
                f"{provider['name']}: "
                f"{type(exc).__name__}: {exc}"
            )
            errors.append(error)
            print("Provider failed:", error)

    raise RuntimeError(
        "All configured AI providers failed:\n"
        + "\n".join(errors)
    )

