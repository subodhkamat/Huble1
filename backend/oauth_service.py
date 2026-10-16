
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from urllib.parse import quote
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from database import BASE_DIR, get_db
from db_model import AuthSession, User
from auth_service import create_session_tokens, hash_token


# Load the backend environment explicitly.
load_dotenv(BASE_DIR / ".env", override=False)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
FRONTEND_URL = config.FRONTEND_URL
COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)
SESSION_TTL_HOURS = int(
    os.getenv("SESSION_TTL_HOURS", "168")
)
print("=== BuildAI OAuth Environment Check ===")
print(f"GOOGLE_CLIENT_ID exists:{GOOGLE_CLIENT_ID}")
print("GOOGLE_CLIENT_SECRET exists:", bool(GOOGLE_CLIENT_SECRET))
print("GOOGLE_CLIENT_ID prefix:", GOOGLE_CLIENT_ID[:12] if GOOGLE_CLIENT_ID else "MISSING")
print("GOOGLE_CLIENT_SECRET length:", len(GOOGLE_CLIENT_SECRET or ""))
print("FRONTEND_URL:", FRONTEND_URL)
print("=======================================")


if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise RuntimeError(
        "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET "
        "must be set in backend/.env"
    )


router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url=(
        "https://accounts.google.com/.well-known/openid-configuration"
    ),
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    raw_token = request.cookies.get("buildai_session")
    print("1b")
    if not raw_token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
    print("2b")
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(raw_token),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid",
        )

    user_result = await db.execute(
        select(User).where(User.id == session.user_id)
    )
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Account is unavailable",
        )

    return user


async def require_csrf(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthSession:
    cookie_token = request.cookies.get("buildai_csrf")
    header_token = request.headers.get("X-CSRF-Token")
    raw_session = request.cookies.get("buildai_session")

    if not cookie_token or not header_token or not raw_session:
        raise HTTPException(
            status_code=403,
            detail="CSRF verification required",
        )

    import hmac

    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=403,
            detail="Invalid CSRF token",
        )

    result = await db.execute(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(raw_session),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()

    if (
        session is None
        or not hmac.compare_digest(
            session.csrf_token, header_token
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid session or CSRF token",
        )

    return session


def _login_error(message: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"{FRONTEND_URL}/?auth_error={quote(message)}",
        status_code=303,
    )


@router.get("/google")
async def google_login(request: Request):
    # Fixed URI: request.url_for() yields 127.0.0.1 vs localhost depending on how
    # the browser reached the API, which Google rejects (redirect_uri_mismatch).
    redirect_uri = config.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(
        request, redirect_uri
    )


@router.get("/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        token = await oauth.google.authorize_access_token(request)
        claims = token.get("userinfo")

        if not claims:
            claims = await oauth.google.userinfo(token=token)

    except Exception as exc:
        print(f"Google OAuth failed: {type(exc).__name__}: {exc}")
        return _login_error("Google sign-in failed. Please try again.")

    google_sub = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified") is True

    if not google_sub or not email or not email_verified:
        return _login_error("Google account must have a verified email.")

    result = await db.execute(
        select(User).where(User.google_sub == google_sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Never silently link a different Google identity to
        # an existing account just because the email matches.
        email_result = await db.execute(
            select(User).where(User.email == email)
        )
        existing_email_user = email_result.scalar_one_or_none()

        if existing_email_user is not None:
            return _login_error(
                "An account with this email already exists "
                "with a different identity."
            )

        user = User(
            email=email,
            display_name=(
                claims.get("name")
                or email.split("@")[0]
            ),
            avatar_url=claims.get("picture"),
            google_sub=google_sub,
            is_active=True,
        )
        db.add(user)
        await db.flush()

    if not user.is_active:
        return _login_error("This account is disabled.")

    # Rotate the session on every successful login.
    session_tokens = create_session_tokens()
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=session_tokens["token_hash"],
        csrf_token=session_tokens["csrf_token"],
        expires_at=session_tokens["expires_at"],
    )
    db.add(auth_session)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    response = RedirectResponse(
        url=f"{FRONTEND_URL}/",
        status_code=303,
    )

   
    response.set_cookie(
        key="buildai_session",
        value=session_tokens["raw_token"],
        httponly=True,
        secure=True,
        samesite="none",
        max_age=SESSION_TTL_HOURS * 60 * 60,
        path="/",
    )

    response.set_cookie(
        key="buildai_csrf",
        value=session_tokens["csrf_token"],
        httponly=False,
        secure=True,
        samesite="none",
        max_age=SESSION_TTL_HOURS * 60 * 60,
        path="/",
    )

    return response


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
):
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
        },
    }


@router.post("/logout")
async def logout(
    session: AuthSession = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(session)
    await db.commit()

    response = JSONResponse({"success": True})
    response.delete_cookie(
        "buildai_session",
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        "buildai_csrf",
        path="/",
        secure=COOKIE_SECURE,
        httponly=False,
        samesite="lax",
    )

    return response