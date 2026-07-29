"""
لایه مشترک اتصال به هوش مصنوعی — از Gemini API گوگل استفاده می‌کند که از طریق
Google AI Studio (aistudio.google.com/apikey) کاملاً رایگان (بدون نیاز به کارت
بانکی) قابل دریافت است و قدرت خوبی برای تولید متن، JSON و تحلیل فارسی دارد.

فقط کافی است متغیر محیطی GEMINI_API_KEY را روی Render تنظیم کنی.
"""
import os
import json
import urllib.request
import urllib.error

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_MODEL = "gemini-2.0-flash"


def has_ai_key() -> bool:
    return bool(os.environ.get(GEMINI_API_KEY_ENV))


def ask_ai(prompt: str, max_tokens: int = 2000, temperature: float = 0.7):
    """
    یک درخواست ساده به Gemini API می‌فرستد و متن پاسخ را برمی‌گرداند.
    در صورت نبود کلید یا بروز هر خطایی (شبکه، سهمیه و ...) مقدار None
    برمی‌گرداند تا بخش‌های دیگر کد به‌صورت خودکار به حالت آفلاین/قانون‌محور
    سوییچ کنند و سایت هیچ‌وقت از کار نیفتد.
    """
    api_key = os.environ.get(GEMINI_API_KEY_ENV)
    if not api_key:
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{DEFAULT_MODEL}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        return text or None
    except Exception:
        return None


def ask_ai_json(prompt: str, max_tokens: int = 2500, temperature: float = 0.7):
    """مثل ask_ai ولی خروجی را به‌صورت JSON پارس‌شده برمی‌گرداند.
    اگر پاسخ JSON معتبر نبود یا کلید موجود نبود، None برمی‌گرداند."""
    text = ask_ai(prompt, max_tokens=max_tokens, temperature=temperature)
    if not text:
        return None
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return None


def ask_ai_vision_json(image_bytes: bytes, mime_type: str, prompt: str, max_tokens: int = 4000, temperature: float = 0.4):
    """مثل ask_ai_json ولی علاوه بر متن، یک عکس (یا صفحه اسکن‌شده) هم به مدل
    می‌دهد تا محتوای تصویری (مثل برگه سوالات دست‌نویس/چاپی) را بخواند و
    خروجی ساخت‌یافته JSON برگرداند. اگر کلید API تنظیم نشده یا خطایی رخ دهد،
    None برمی‌گرداند."""
    api_key = os.environ.get(GEMINI_API_KEY_ENV)
    if not api_key:
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{DEFAULT_MODEL}:generateContent?key={api_key}"
    )
    import base64
    b64_data = base64.b64encode(image_bytes).decode("ascii")

    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": b64_data}},
            ],
        }],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            return None
        cleaned = text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception:
        return None


def ask_ai_conversation(messages, system_instruction: str = None, max_tokens: int = 2000, temperature: float = 0.7):
    """
    برای گفت‌وگوی چندمرحله‌ای (مثل چت مشاوره) که باید تاریخچه پیام‌های قبلی
    را هم به یاد داشته باشد.
    messages: لیستی از {"role": "user"|"assistant", "text": "..."}
    system_instruction: دستورالعمل ثابت لحن/شخصیت (اختیاری)
    خروجی: متن پاسخ یا None (در صورت نبود کلید یا بروز خطا)
    """
    api_key = os.environ.get(GEMINI_API_KEY_ENV)
    if not api_key:
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{DEFAULT_MODEL}:generateContent?key={api_key}"
    )
    contents = []
    for m in messages:
        role = "user" if m.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.get("text", "")}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        return text or None
    except Exception:
        return None
