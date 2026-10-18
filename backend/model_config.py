
import json
from pathlib import Path, PurePosixPath
from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
import json
from openai import APIStatusError, APIConnectionError
import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
load_dotenv()
# Provider setup: Groq first, OpenRouter free-model router as fallback.
# Put keys in backend/.env. Missing keys are skipped.
providers = []

groq_key = os.getenv("GROQ_API_KEY")
groq_key1=os.getenv("GROQ_API_KEY1")
if groq_key:
    providers.append({
        "name": "Groq",
        "client": AsyncOpenAI(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
        ),
        "model": os.getenv("AI_MODEL", "openai/gpt-oss-20b"),
        "json_mode": True,
    })

if groq_key1:
    providers.append({
        "name": "Groq1",
        "client": AsyncOpenAI(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
        ),
        "model": os.getenv("AI_MODEL", "openai/gpt-oss-20b"),
        "json_mode": True,
    })

openrouter_key = os.getenv("OPENROUTER_API_KEY")
if openrouter_key:
    providers.append({
        "name": "OpenRouter",
        "client": AsyncOpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        ),
        "model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
        # The free router may select models with differing JSON-mode support.
        "json_mode": False,
    })

if not providers:
    raise RuntimeError(
        "No AI provider configured. Add GROQ_API_KEY and/or "
        "OPENROUTER_API_KEY to backend/.env"
    )


async def create_completion_with_fallback(messages, *, max_tokens=20000, temperature=0.2):
    """Try configured providers in order; fall back on quota, connection,
    or temporary server errors. Returns (response, provider_name).
    """
    failures = []
    a=1
    for provider in providers:
        try:
            print(f",model-{a}")
            kwargs = {
                "model": provider["model"],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if provider["json_mode"]:
                kwargs["response_format"] = {"type": "json_object"}

            response = await provider["client"].chat.completions.create(**kwargs)
            return response, provider["name"]

        except APIConnectionError as exc:
            failures.append(f'{provider["name"]}: connection error: {exc}')
            continue
        except APIStatusError as exc:
            status = exc.status_code
            # Move to the next provider for rate limits, temporary failures,
            # and unsupported model/request features. Do not hide other errors.
            if status in (400, 401, 403, 404, 408, 429, 500, 502, 503, 504):
                failures.append(f'{provider["name"]}: HTTP {status}: {exc}')
                continue
            raise

    raise RuntimeError(
        "All configured AI providers failed. " + " | ".join(failures)
    )

SYSTEM_PROMPT = """
You are a senior full-stack engineer inside an AI-powered
application builder.
Your task is to generate a complete, runnable React + Vite
project that satisfies the user's requirements.
OUTPUT RULES:
1. Return ONLY one valid JSON object.
2. The JSON must contain a "files" object mapping relative
   file paths to complete file contents as strings.
3. Include package.json, index.html, src/main.jsx,
   src/App.jsx, and src/App.css.
4. Every generated file must be complete and syntactically valid.
5. Escape newlines, quotes, and special characters correctly
   so the output can be parsed using JSON.parse().
6. Never wrap the JSON in Markdown fences.
7. Never include explanations outside the JSON object.
PROJECT RULES:
8. Use React functional components and hooks.
9. Use modern, maintainable JSX and reusable components.
10. Build a polished, responsive, accessible user interface.
11. Use modern CSS with consistent spacing, typography,
    colours, shadows, borders, and interaction states.
12. All buttons, forms, navigation elements, and controls
    must have meaningful functionality.
13. Use local React state for frontend-only interactions.
14. Use only dependencies declared in package.json.
15. Keep dependencies minimal and mutually compatible.
16. Never expose API keys, credentials, or environment secrets.
17. Never use absolute paths or paths containing "..".
18. Do not claim that mocked backend functionality is real.
19. Ensure imports, exports, filenames, and component references
    are consistent across the project.
20. Do not overwrite required functionality with placeholder code.
EXPECTED FORMAT:
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

SYSTEM_PROMPT2 = """
You are a senior UI/UX designer and expert React frontend
engineer working inside an AI application builder.
Your task is to modernize an EXISTING React + Vite project
using the provided project files, user requirements, and
design instructions.

PRIMARY OBJECTIVE:
Transform the existing interface into a polished, modern,
professional, visually appealing, responsive application
while preserving all existing functionality.

1. INSPECT BEFORE EDITING
- Read the provided src/App.jsx, src/main.jsx, index.html,
  CSS files, package.json, and other relevant components.
- Understand the existing component structure, imports,
  state management, routing, and interactions.
- Identify the files that actually need changes.
- Do not assume the project structure without inspecting it.

2. MODERN UI/UX DESIGN
- Use a consistent design system with a deliberate colour
  palette, typography, spacing, borders, and shadows.
- Create a visually polished interface with strong hierarchy.
- Use modern layouts, cards, grids, navigation, and whitespace
  where appropriate for the application.
- Add tasteful gradients, subtle animations, hover states,
  transitions, and micro-interactions when they improve UX.
- Avoid excessive gradients, random colours, clutter,
  unnecessary animations, and generic template-like designs.
- Make the interface look intentional and production-quality.
3. REACT AND COMPONENTS
- Use clean, idiomatic React JSX and functional components.
- Keep components reusable and code maintainable.
- Preserve existing state, event handlers, API integrations,
  routing, props, and business logic.
- Do not replace working features with static mockups.
- Do not remove existing functionality simply to simplify code.

4. CSS REQUIREMENTS
- Prefer the project's existing styling approach.
- Improve the existing CSS instead of replacing it blindly.
- Use responsive layouts for mobile, tablet, and desktop.
- Include accessible focus states and useful hover states.
- Prevent overflow, broken layouts, and inconsistent spacing.
- Avoid unnecessary global CSS that could break other pages.
- Keep class names consistent with the JSX.

5. ICONS AND LIBRARIES
- Prefer lucide-react for clean, consistent interface icons.
- First inspect package.json to determine which dependencies
  are already installed.
- Do not import a library that is not installed.
- If a new dependency is genuinely necessary, add it to
  package.json and use a compatible version.
- Prefer CSS and existing project capabilities over adding
  unnecessary UI frameworks.
- Do not use emojis as a substitute for professional icons
  unless the design specifically calls for them.

6. FILE MODIFICATION RULES
- Modify src/App.jsx, src/App.css, src/main.jsx, index.html,
  and other existing files only when needed.
- Preserve the existing entry point and application setup.
- Do not regenerate the entire project when only a few files
  require modifications.
- Do not create duplicate CSS files or duplicate components.
- Never invent missing source code or pretend to have inspected
  files that were not provided.
- Return complete contents for every modified file.

7. QUALITY CHECKS
Before returning the result, verify that:
- JSX and JavaScript syntax are valid.
- Imports and exports match.
- CSS selectors match the JSX.
- Dependencies used by imports are declared.
- Existing application behaviour is preserved.
- The layout is responsive and accessible.
- No secrets or unrelated files are introduced.
8. OUTPUT FORMAT
Return ONLY valid JSON with this structure:
{
  "files": {
    "src/App.jsx": "complete file contents",
    "src/App.css": "complete file contents"
  }
}
Include every modified file, using its actual relative path.
Include src/main.jsx, index.html, or package.json only when
they genuinely need changes.
Return the complete contents of each modified file, not a
diff, patch, explanation, or partial snippet.
Do not wrap the JSON in Markdown fences.
Do not output anything outside the JSON object.
"""
# -------------------- STATE --------------------

class State(TypedDict, total=False):

    prompt: str
    files: dict[str, str]
    result: dict[str, Any]
# -------------------- JSON PARSER --------------------


import json
import re


def parse_model_json(content, response, agent_name: str) -> dict:
    if not content or not content.strip():
        raise ValueError(f"{agent_name} returned an empty response.")

    if response.choices[0].finish_reason == "length":
        raise ValueError(
            f"{agent_name} response was truncated. "
            "Reduce the input size or generate fewer files."
        )

    content = content.strip()

    # Remove Markdown fences if the model ignores the JSON-only rule.
    if content.startswith("```"):
        content = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            content,
            flags=re.IGNORECASE,
        ).strip()

    print(f"{agent_name}: parsing JSON...")
    print("1p: Response length:", len(content))
    print("1p-a: Response starts with:", repr(content[:150]))

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{agent_name} returned invalid JSON at "
            f"line {exc.lineno}, column {exc.colno}. "
            f"Nearby content: {content[max(0, exc.pos-150):exc.pos+150]!r}"
        ) from exc

    print("2p: JSON parsed successfully")

    if not isinstance(result, dict):
        raise ValueError(f"{agent_name} must return a JSON object.")

    files = result.get("files")

    if not isinstance(files, dict) or not files:
        raise ValueError(
            f"{agent_name} must return a non-empty 'files' object."
        )

    # Recover files whose contents were accidentally double-escaped.
    # Only apply this when the file contains no real newlines.
    for path, value in files.items():
        if not isinstance(value, str):
            raise ValueError(f"Invalid content for file: {path}")

        if "\n" not in value and value.count(r"\n") >= 3:
            value = (
                value.replace(r"\r\n", "\n")
                .replace(r"\n", "\n")
                .replace(r"\t", "\t")
                .replace(r'\"', '"')
            )
            files[path] = value
            print(f"3p: Normalized escaped contents: {path}")

    print("4p: Parsed files:", list(files.keys()))

    return result


# -------------------- FILE VALIDATION --------------------
REQUIRED_FILES = {
    "package.json",
    "index.html",
    "src/main.jsx",
    "src/App.jsx",
    "src/App.css",
}
ALLOWED_FILES = REQUIRED_FILES

def validate_files(files: dict, require_core_files: bool = False):

    if not isinstance(files, dict) or not files:
        raise ValueError("The AI returned no project files.")
    if require_core_files:
        missing = REQUIRED_FILES - files.keys()
        if missing:
            raise ValueError(
                f"Missing required files: {sorted(missing)}"
            )

    for path, file_content in files.items():
        if not isinstance(path, str) or not path.strip():

            raise ValueError("Invalid file path returned by the model.")
        normalized = path.replace("\\\\", "/")
        parsed = PurePosixPath(normalized)
        if (
            parsed.is_absolute()
            or ".." in parsed.parts
            or ":" in normalized
            or normalized.startswith("/")
            or not isinstance(file_content, str)
        ):
            raise ValueError(f"Unsafe path or invalid contents: {path}")
        if not (
            normalized in ALLOWED_FILES
            or normalized.startswith("src/")
        ):
            raise ValueError(
                f"File is outside the allowed frontend scope: {path}"
            )
# -------------------- TOOL 1: PROJECT GENERATOR --------------------

async def superbot(state: State) -> dict:

    prompt = state["prompt"]
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
            + """

OUTPUT FORMAT — MANDATORY:
Return exactly one valid JSON object.
The object must have this structure:
{

  "files": {
    "package.json": "complete file contents",
    "index.html": "complete file contents",
    "src/main.jsx": "complete file contents",
    "src/App.jsx": "complete file contents",
    "src/App.css": "complete file contents"
  }
}
Return JSON only, without Markdown fences or explanations.
Do not omit required files.
""",
        },
        {"role": "user", "content": prompt},
    ]
    try:
        response, provider_name = await create_completion_with_fallback(
            messages,
            max_tokens=20000,
            temperature=0.2,
        )
    except RuntimeError as exc:
        raise RuntimeError(f"Superbot generation failed: {exc}") from exc
    content = response.choices[0].message.content
    project = parse_model_json(

        content,
        response,
        "Superbot",
    )
    files = project.get("files")
    if not isinstance(files, dict):

        raise ValueError(

            "Superbot response must contain a 'files' object."
        )
    validate_files(files, require_core_files=True)
    return {"result": project}

# -------------------- TOOL 2: UI MODERNIZER --------------------
async def ui_modernizer(state: State) -> dict:

    prompt = state.get("prompt", "")
    print(f"{prompt}")
    existing_files = state.get("files", {})
    print("1c")
    if not isinstance(existing_files, dict) or not existing_files:
        raise ValueError(
            "No existing project files provided to the UI modernizer."
        )
    user_message = f"""
    
User's design requirements:

{prompt}

Existing project files:

{json.dumps(existing_files, ensure_ascii=False)}
Modernize the existing project according to the system instructions.
Preserve existing functionality and return only files that need changes.
Return a JSON object with a top-level "files" object.
Each file value must be a complete replacement source-code string.
Do not return Markdown fences.

"""
    response, provider_name = await create_completion_with_fallback(
        [
            {"role": "system", "content": SYSTEM_PROMPT2},
            {"role": "user", "content": user_message},
        ],
        max_tokens=20000,
        temperature=0.2,
    )
    print("2c")
    result = parse_model_json(
        response.choices[0].message.content,
        response,
        "UI modernizer",
    )
    print("3c")
    modified_files = result.get("files")
    if not isinstance(modified_files, dict) or not modified_files:
        raise ValueError(
            "UI modernizer must return a non-empty 'files' object."
        )
    validate_files(modified_files)
    return {
        "result": {
            "files": modified_files,
            "modified_paths": list(modified_files.keys()),
        }
    }

# -------------------- MERGE MODERNIZED FILES --------------------
async def run_ui_modernizer(state: State) -> dict:
    print("m1")
    project = state.get("result", {})
    print("2m")
    files = project.get("files", {})
    if not files:
        raise ValueError("Superbot did not return any project files.")
    
    modernized = await ui_modernizer({
        "prompt": state.get("prompt", ""),
        "files": files,
    })
    print("3m")
    modified_files = modernized["result"]["files"]
    # Preserve original files and replace only modified files.
    print("4m")
    updated_files = files.copy()
    print("5m")
    updated_files.update(modified_files)
    return {
        "result": {
            "files": updated_files,
            "modified_paths": list(modified_files.keys()),
        }
    }

# -------------------- LANGGRAPH WORKFLOW --------------------

ai_builder = StateGraph(State)

ai_builder.add_node("superbot", superbot)
ai_builder.add_node("ui_modernizer", run_ui_modernizer)
ai_builder.add_edge(START, "superbot")
ai_builder.add_edge("superbot", "ui_modernizer")
ai_builder.add_edge("ui_modernizer", END)

app = ai_builder.compile()

# -------------------- RUN THE AGENT --------------------
async def generate_project1(prompt: str) -> dict[str, str]:

    """Generate a React project and return its files."""
    print("1a")
    if not prompt or not prompt.strip():

        raise ValueError("Project prompt cannot be empty.")
    print("2a")
    result = await app.ainvoke({
        "prompt": prompt.strip()
    })
    print("3a")
    project_files = result.get("result", {}).get("files")
    print("4a")
    validate_files(project_files, require_core_files=True)

    return project_files