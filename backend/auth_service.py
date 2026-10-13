
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
import os

load_dotenv()

SESSION_TTL_HOURS = int(
    os.getenv("SESSION_TTL_HOURS", "168")
)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session_tokens():
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)

    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=SESSION_TTL_HOURS
    )

    return {
        "raw_token": raw_token,
        "token_hash": hash_token(raw_token),
        "csrf_token": csrf_token,
        "expires_at": expires_at,
    }