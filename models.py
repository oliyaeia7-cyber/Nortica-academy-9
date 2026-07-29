from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=False, unique=True, index=True)
    email = Column(String(200), nullable=False, unique=True, index=True)  # ایمیل (اجباری، برای بازیابی رمز عبور)
    password_hash = Column(String(255), nullable=True)   # هش رمز عبور (PBKDF2)
    field = Column(String(100), nullable=False)          # گروه تحصیلی (رشته)
    grade = Column(String(20), nullable=False)            # پایه (دهم/یازدهم/دوازدهم)
    target_major = Column(String(200), nullable=True)     # رشته هدف دانشگاهی
    target_university = Column(String(200), nullable=True)
    daily_hours = Column(Float, default=2.0)              # تعداد ساعت مطالعه روزانه
    created_at = Column(DateTime, default=datetime.utcnow)

    study_logs = relationship("StudyLog", back_populates="user", cascade="all, delete-orphan")
    exam_results = relationship("ExamResult", back_populates="user", cascade="all, delete-orphan")
    plans = relationship("StudyPlan", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    plan_type = Column(String(20))   # week / month / six_month / year
    content = Column(JSON)           # ساختار کامل برنامه (روز به روز)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="plans")


class StudyLog(Base):
    __tablename__ = "study_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    hours = Column(Float, default=0.0)
    subject = Column(String(150), nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="study_logs")


class ExamResult(Base):
    __tablename__ = "exam_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subject = Column(String(150))
    lesson = Column(String(150), nullable=True)
    question_count = Column(Integer)
    correct_count = Column(Integer)
    score_percent = Column(Float)
    taken_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="exam_results")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    phone = Column(String(20))
    subject = Column(String(200))
    message = Column(Text)
    status = Column(String(20), default="در حال بررسی")
    created_at = Column(DateTime, default=datetime.utcnow)


class SiteContactInfo(Base):
    """اطلاعات تماس بخش پشتیبانی (آدرس، کانال تلگرام/بله، تلفن شرکت).
    یک ردیف ثابت (id=1) که از پنل مدیریت قابل ویرایش و پاک‌کردن است؛
    پیش‌فرض همه‌چیز خالی است تا فقط خودتان تکمیلش کنید."""
    __tablename__ = "site_contact_info"

    id = Column(Integer, primary_key=True, index=True)
    office_address = Column(String(500), nullable=True, default="")
    telegram_channel = Column(String(300), nullable=True, default="")
    bale_channel = Column(String(300), nullable=True, default="")
    instagram_channel = Column(String(300), nullable=True, default="")
    company_phone = Column(String(50), nullable=True, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PasswordResetCode(Base):
    """کد ۶ رقمی بازیابی رمز عبور که به ایمیل کاربر ارسال می‌شود.
    هر کد فقط تا مدت محدودی معتبر و فقط یک‌بار مصرف است."""
    __tablename__ = "password_reset_codes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    email = Column(String(200), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class BlogPost(Base):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(250), unique=True, index=True, nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # فیلدهای جدید و اختیاری برای پنل مدیریت کامل‌تر: تصویر کاور و لینک اختصاصی مقاله
    image_url = Column(String(300), nullable=True)
    link_url = Column(String(500), nullable=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    plan_id = Column(String(30), default="free_week")
    plan_title = Column(String(100), default="برنامه هفتگی رایگان")
    is_active = Column(Integer, default=1)
    started_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscription")


# ---------------------------------------------------------------------------
# مدل‌های جدید برای پنل مدیریت کامل‌تر (کتابخانه رسانه و مدیریت لینک‌ها)
# ---------------------------------------------------------------------------

class MediaAsset(Base):
    """کتابخانه رسانه: تصاویر آپلودشده از پنل ادمین، به‌صورت base64 در دیتابیس
    ذخیره می‌شوند (هماهنگ با معماری فعلی پروژه که لوگو هم به همین شکل است)."""

    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(300), nullable=True)
    content_type = Column(String(100), nullable=False)
    data_b64 = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SiteLink(Base):
    """لینک‌های دلخواه سایت (مثل شبکه‌های اجتماعی یا لینک‌های سفارشی) که از
    پنل ادمین قابل مدیریت هستند."""

    __tablename__ = "site_links"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    url = Column(String(500), nullable=False)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionBankItem(Base):
    """بانک سوالات آزمون (جایگزین تولید سوال با هوش مصنوعی در لحظه). سوالاتی که
    از پنل ادمین اضافه می‌شوند source='manual' دارند و در اولویت انتخاب برای
    آزمون هستند؛ اگر برای یک ترکیب پایه/درس/فصل/سطح سوال دستی کافی نباشد، از
    موتور تولید خودکار مبتنی بر سرفصل واقعی کتاب درسی (curriculum.py) به عنوان
    مکمل استفاده می‌شود."""

    __tablename__ = "question_bank"

    id = Column(Integer, primary_key=True, index=True)
    grade = Column(String(30), index=True, nullable=False)
    subject = Column(String(150), index=True, nullable=False)
    lesson = Column(String(200), index=True, nullable=True)
    difficulty = Column(String(20), index=True, default="متوسط")
    question_type = Column(String(20), default="تستی")  # تستی / تشریحی
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=True)   # JSON لیست ۴ گزینه (فقط تستی)
    correct_index = Column(Integer, nullable=True)  # فقط تستی
    model_answer = Column(Text, nullable=True)   # فقط تشریحی
    source = Column(String(20), default="manual")  # manual (از پنل ادمین)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConsultationMessage(Base):
    """پیام‌های چت «مشاوره تحصیلی هوشمند نورتیکا». هر پیام یا از طرف کاربر
    است یا از طرف دستیار هوشمند؛ تاریخچه بر اساس user_id بازیابی می‌شود."""

    __tablename__ = "consultation_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(12), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UniversityMajorCode(Base):
    """بانک کدرشته‌های دانشگاهی — از پنل ادمین (تکی یا با آپلود CSV دفترچه
    سازمان سنجش) پر می‌شود. موتور «انتخاب رشته هوشمند نورتیکا» ابتدا از این
    داده‌های واقعی برای معرفی دانشگاه استفاده می‌کند؛ اگر داده کافی برای یک
    ترکیب رتبه/رشته/شهر نبود، به‌عنوان مکمل از هوش مصنوعی (با ذکر این‌که
    تخمینی است) کمک می‌گیرد."""

    __tablename__ = "university_major_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(30), index=True, nullable=True)          # کد رشته محل
    university_name = Column(String(300), index=True, nullable=False)
    major_name = Column(String(300), index=True, nullable=False)  # نام رشته
    city = Column(String(100), index=True, nullable=True)
    ownership_type = Column(String(30), index=True, nullable=True)  # دولتی/آزاد/غیرانتفاعی/پیام‌نور/شبانه
    field_group = Column(String(50), index=True, nullable=True)     # ریاضی/تجربی/انسانی/هنر/زبان
    min_rank = Column(Integer, nullable=True)
    max_rank = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MajorSelectionRequest(Base):
    """درخواست‌های ثبت‌شده در صفحه «انتخاب رشته هوشمند نورتیکا» — برای
    بازتولید PDF و مرور از پنل ادمین نگه‌داری می‌شود."""

    __tablename__ = "major_selection_requests"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=True)
    grade = Column(String(20), nullable=True)
    diploma_rank = Column(Float, nullable=True)  # نمره دیپلم (۰ تا ۲۰)
    konkur_rank = Column(Integer, nullable=True)
    target_field = Column(String(200), nullable=True)
    target_city = Column(String(100), nullable=True)
    extra_text = Column(Text, nullable=True)
    result_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PricingPlan(Base):
    """پلن‌های اشتراک سایت — از پنل ادمین قابل ویرایش هستند (به‌جای مقادیر
    ثابت در کد). plan_key همان شناسه‌ای است که در subscription استفاده
    می‌شود و باید یکتا بماند."""

    __tablename__ = "pricing_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_key = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(150), nullable=False)
    duration = Column(String(30), nullable=True)
    description = Column(String(500), nullable=True)
    price = Column(Integer, default=0)
    price_label = Column(String(100), nullable=True)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
