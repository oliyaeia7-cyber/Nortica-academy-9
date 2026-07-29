# ---------------------------------------------------------------------------
# Dockerfile برای نورتیکا (Noortika) — پروژه‌ی تخت FastAPI، آماده‌ی Render
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# جلوگیری از تولید فایل .pyc و بافر نشدن لاگ‌ها (لاگ‌های Render فوری دیده شوند)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# نصب وابستگی‌ها ابتدا (استفاده از cache لایه‌ی Docker در بیلدهای بعدی)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل کد پروژه (ساختار تخت — بدون زیرپوشه)
COPY . .

# پوشه‌ی دیتابیس محلی SQLite (فقط برای اجرای بدون DATABASE_URL/توسعه؛ روی
# Render طبق render.yaml یک دیتابیس PostgreSQL پایدار وصل می‌شود، طبق
# database.py: اگر DATABASE_URL تنظیم باشد همان استفاده می‌شود)
RUN mkdir -p /app/data

# Render خودش متغیر PORT را در زمان اجرا تزریق می‌کند؛ ۱۰۰۰۰ فقط مقدار پیش‌فرض
# محلی است تا `docker run` بدون تنظیم PORT هم کار کند.
ENV PORT=10000
EXPOSE 10000

# اجرای سرور با uvicorn؛ از شکل shell استفاده شده تا ${PORT} در زمان اجرا
# توسط Render جایگزین شود.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
