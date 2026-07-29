import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

os.makedirs("data", exist_ok=True)

# اگر متغیر محیطی DATABASE_URL تنظیم شده باشد (مثلاً وقتی یک دیتابیس PostgreSQL
# پایدار روی Render وصل شده)، از همان استفاده می‌کنیم تا اطلاعات بعد از
# خواب/بیدار شدن یا هر دیپلوی جدید سرویس هم پاک نشوند. در غیر این صورت،
# برای اجرای محلی/توسعه از همان SQLite ساده استفاده می‌شود.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/noortika.db")

# Render (و بسیاری از سرویس‌های دیگر) آدرس Postgres را با پیشوند قدیمی
# "postgres://" می‌دهند که SQLAlchemy 1.4+/2.0 آن را نمی‌پذیرد؛ باید به
# "postgresql://" تبدیل شود.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# check_same_thread فقط برای SQLite لازم است.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
