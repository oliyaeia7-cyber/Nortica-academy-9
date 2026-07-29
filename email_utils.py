"""
ارسال ایمیل برای نورتیکا (مثلاً کد بازیابی رمز عبور).

با تنظیم متغیرهای محیطی زیر روی Render (یا هر هاست دیگر)، ارسال ایمیل واقعی
فعال می‌شود؛ اگر تنظیم نشوند، به‌جای خطا دادن، کد در لاگ سرور چاپ می‌شود تا
در حالت توسعه/تست هم بدون تنظیم SMTP بشود کار را جلو برد:

    SMTP_HOST       آدرس سرور SMTP (مثلاً smtp.gmail.com)
    SMTP_PORT       پورت (پیش‌فرض 587)
    SMTP_USER       نام کاربری/ایمیل فرستنده
    SMTP_PASSWORD   رمز عبور یا App Password
    SMTP_FROM       آدرس فرستنده (اگر خالی باشد از SMTP_USER استفاده می‌شود)
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def is_smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def send_email(to_email: str, subject: str, body_text: str) -> bool:
    """ایمیل را ارسال می‌کند. اگر SMTP تنظیم نشده باشد، به‌جای کرش کردن، فقط
    در لاگ سرور چاپ می‌کند و False برمی‌گرداند (فراخوان می‌تواند این حالت را
    برای دیباگ در نظر بگیرد)."""
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM") or user

    if not host or not user or not password:
        print(f"[email_utils] SMTP تنظیم نشده — به‌جای ارسال واقعی، متن ایمیل در لاگ چاپ می‌شود.")
        print(f"[email_utils] To: {to_email} | Subject: {subject}\n{body_text}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body_text)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"[email_utils] ارسال ایمیل با خطا مواجه شد: {exc}")
        print(f"[email_utils] To: {to_email} | Subject: {subject}\n{body_text}")
        return False
