import hashlib
import hmac
import os


def hash_password(raw_password: str) -> str:
    """رمز عبور را با PBKDF2-HMAC-SHA256 و سالت تصادفی هش می‌کند (بدون نیاز به کتابخانه خارجی)."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(raw_password: str, stored: str) -> bool:
    """رمز واردشده را با هش ذخیره‌شده مقایسه می‌کند."""
    if not stored or "$" not in stored:
        return False
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(actual, expected)
