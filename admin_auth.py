"""
احراز هویت ساده‌ی پنل ادمین.

- رمز عبور از متغیر محیطی ADMIN_PASSWORD خوانده می‌شود (روی Render تنظیم کن).
- بعد از ورود موفق، یک کوکی امضاشده (HMAC-SHA256) و httponly روی مرورگر
  ست می‌شود که سمت سرور اعتبارسنجی می‌گردد؛ رمز عبور هیچ‌وقت داخل کوکی
  ذخیره نمی‌شود، فقط یک امضا با انقضای زمانی.
- کلید امضا (_SECRET) هر بار سرور بالا می‌آید به‌صورت تصادفی ساخته می‌شود؛
  یعنی با هر ری‌استارت/دیپلوی، نشست‌های قبلی نامعتبر می‌شوند و باید دوباره
  وارد شوی (طبیعی و بی‌خطر است).
"""
import hmac
import hashlib
import os
import secrets
import time
from fastapi import Request, HTTPException

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
_SECRET = secrets.token_hex(32)

COOKIE_NAME = "noortika_admin_session"
TOKEN_TTL_SECONDS = 60 * 60 * 12  # ۱۲ ساعت


def _sign(value: str) -> str:
    return hmac.new(_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    ts = str(int(time.time()))
    return f"{ts}.{_sign(ts)}"


def is_valid_token(token) -> bool:
    if not token or "." not in token:
        return False
    ts, sig = token.split(".", 1)
    if not hmac.compare_digest(_sign(ts), sig):
        return False
    try:
        issued = int(ts)
    except ValueError:
        return False
    return (time.time() - issued) < TOKEN_TTL_SECONDS


def is_logged_in(request: Request) -> bool:
    return is_valid_token(request.cookies.get(COOKIE_NAME))


def require_admin(request: Request) -> None:
    """Dependency برای محافظت از route/API های ادمین."""
    if not ADMIN_PASSWORD:
        raise HTTPException(
            status_code=503,
            detail="رمز عبور ادمین روی سرور تنظیم نشده است (ADMIN_PASSWORD).",
        )
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="ابتدا از /admin/login وارد پنل ادمین شو.")
