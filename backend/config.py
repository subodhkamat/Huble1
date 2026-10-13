import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)


def clean_url(value: str | None, default: str) -> str:
    """Strip whitespace, quotes and trailing slashes from a URL setting.

    A stray space or trailing slash in .env (e.g. FRONTEND_URL=" http://localhost:5173/")
    silently breaks CORS and OAuth redirects, so normalise it once, here.
    """
    value = (value or "").strip().strip("\"'").strip()
    return (value or default).rstrip("/")


FRONTEND_URL = clean_url(os.getenv("FRONTEND_URL"), "http://localhost:5173")
BACKEND_URL = clean_url(os.getenv("BACKEND_URL"), "http://localhost:8000")

# Must be listed under "Authorized redirect URIs" in Google Cloud Console.
GOOGLE_REDIRECT_URI = (
    os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    or f"{BACKEND_URL}/auth/google/callback"
)
