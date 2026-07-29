from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth_utils import hash_password, verify_password
import models, schemas
import re
import secrets
from datetime import datetime, timedelta
import email_utils

router = APIRouter(prefix="/api/users", tags=["users"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("")
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    email_normalized = payload.email.strip().lower()
    if not EMAIL_RE.match(email_normalized):
        raise HTTPException(status_code=400, detail="ایمیل وارد شده معتبر نیست.")

    existing_phone = db.query(models.User).filter(models.User.phone == payload.phone).first()
    if existing_phone:
        # شماره تلفن قبلاً ثبت‌نام کرده -> باید از فرم ورود استفاده کند، نه ثبت‌نام مجدد
        raise HTTPException(
            status_code=409,
            detail="این شماره تلفن قبلاً ثبت‌نام کرده است. لطفاً از فرم ورود استفاده کنید.",
        )

    existing_email = db.query(models.User).filter(models.User.email == email_normalized).first()
    if existing_email:
        raise HTTPException(status_code=409, detail="این ایمیل قبلاً برای یک حساب دیگر استفاده شده است.")

    data = payload.dict()
    raw_password = data.pop("password")
    data["email"] = email_normalized

    user = models.User(password_hash=hash_password(raw_password), **data)
    db.add(user)
    db.commit()
    db.refresh(user)

    sub = models.Subscription(user_id=user.id, plan_id="free_week", plan_title="برنامه هفتگی رایگان")
    db.add(sub)
    db.commit()

    return {"user_id": user.id, "message": "ثبت‌نام شما با موفقیت انجام شد! 🎉"}


@router.post("/login")
def login_user(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == payload.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="حسابی با این شماره تلفن پیدا نشد. لطفاً ابتدا ثبت‌نام کنید.")

    if not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="شماره تلفن یا رمز عبور اشتباه است.")

    return {"user_id": user.id, "full_name": user.full_name, "message": "ورود با موفقیت انجام شد. خوش آمدید! 👋"}


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")
    return {
        "id": user.id,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "field": user.field,
        "grade": user.grade,
        "target_major": user.target_major,
        "target_university": user.target_university,
        "daily_hours": user.daily_hours,
    }


# ---------------------------------------------------------------------
# فراموشی رمز عبور: کاربر ایمیلی که با آن ثبت‌نام کرده را وارد می‌کند،
# کد ۶ رقمی به همان ایمیل ارسال می‌شود، سپس تغییر رمز با آن کد
# ---------------------------------------------------------------------

RESET_CODE_TTL_MINUTES = 2


@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    email_normalized = payload.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email_normalized).first()
    if not user:
        raise HTTPException(status_code=404, detail="حسابی با این ایمیل پیدا نشد.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_CODE_TTL_MINUTES)

    reset_row = models.PasswordResetCode(
        user_id=user.id, email=email_normalized, code=code, used=False, expires_at=expires_at,
    )
    db.add(reset_row)
    db.commit()

    email_utils.send_email(
        to_email=email_normalized,
        subject="کد بازیابی رمز عبور نورتیکا",
        body_text=(
            f"سلام {user.full_name}،\n\n"
            f"کد بازیابی رمز عبور شما در نورتیکا: {code}\n"
            f"این کد تا {RESET_CODE_TTL_MINUTES} دقیقه دیگر معتبر است.\n"
            f"اگر این درخواست را شما نداده‌اید، این ایمیل را نادیده بگیرید."
        ),
    )

    return {
        "message": f"کد ۶ رقمی به ایمیل {email_normalized} ارسال شد.",
        "ttl_seconds": RESET_CODE_TTL_MINUTES * 60,
    }


def _get_valid_reset_row(db: Session, email_normalized: str, code: str):
    user = db.query(models.User).filter(models.User.email == email_normalized).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    reset_row = (
        db.query(models.PasswordResetCode)
        .filter(models.PasswordResetCode.user_id == user.id, models.PasswordResetCode.code == code)
        .order_by(models.PasswordResetCode.created_at.desc())
        .first()
    )
    if not reset_row:
        raise HTTPException(status_code=400, detail="کد وارد شده نامعتبر است.")
    if reset_row.used:
        raise HTTPException(status_code=400, detail="این کد قبلاً استفاده شده است. دوباره درخواست کد بدهید.")
    if reset_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="زمان این کد تمام شده است. دوباره درخواست کد بدهید.")

    return user, reset_row


@router.post("/verify-reset-code")
def verify_reset_code(payload: schemas.VerifyResetCodeRequest, db: Session = Depends(get_db)):
    email_normalized = payload.email.strip().lower()
    code = payload.code.strip()
    _get_valid_reset_row(db, email_normalized, code)
    return {"message": "کد تایید شد."}


@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    email_normalized = payload.email.strip().lower()
    code = payload.code.strip()

    user, reset_row = _get_valid_reset_row(db, email_normalized, code)

    if len(payload.new_password) < 4:
        raise HTTPException(status_code=400, detail="رمز عبور جدید باید حداقل ۴ کاراکتر باشد.")

    user.password_hash = hash_password(payload.new_password)
    reset_row.used = True
    db.commit()

    return {
        "message": "رمز عبور با موفقیت تغییر کرد. حالا با شماره تلفن و رمز جدید وارد شوید.",
        "phone": user.phone,
    }
