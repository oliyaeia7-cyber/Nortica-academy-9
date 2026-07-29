"""
مشاوره تحصیلی هوشمند نورتیکا — یک چت مشاوره‌ای که با لحن گرم، همدلانه و
انسانی صحبت می‌کند (نه خشک و ربات‌گونه)، ولی هرگز صریحاً ادعای انسان‌بودن
نمی‌کند؛ اگر کاربر مستقیم بپرسد «تو هوش مصنوعی هستی یا انسان؟»، صادقانه
می‌گوید که مشاور تحصیلی هوشمند (مبتنی بر هوش مصنوعی) نورتیکا است.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import ai_client
import models
import schemas
from database import get_db

router = APIRouter(prefix="/api/consultation", tags=["consultation"])

HISTORY_LIMIT = 20  # حداکثر تعداد پیام قبلی که به‌عنوان حافظه گفت‌وگو ارسال می‌شود

SYSTEM_INSTRUCTION_TEMPLATE = """تو «مشاوره تحصیلی هوشمند نورتیکا» هستی؛ یک مشاور تحصیلی گرم، دلسوز و باتجربه
که با دانش‌آموزان ایرانی صحبت می‌کنی. لحن تو باید کاملاً صمیمی، انسانی، همدلانه و
طبیعی باشد — دقیقاً مثل یک مشاور تحصیلی مهربان که واقعاً به آینده دانش‌آموز اهمیت
می‌دهد، نه یک ربات رسمی و خشک. از جملات کوتاه، زبان محاوره‌ای محترمانه و دلگرم‌کننده
استفاده کن.

قوانین مهم:
1. هرگز دروغ نگو و هرگز ادعا نکن که «انسان» هستی. اگر دانش‌آموز مستقیماً پرسید
   «تو هوش مصنوعی هستی؟» یا «آدمی یا ربات؟» یا مشابه آن، صادقانه و بدون خجالت
   بگو: «من مشاوره تحصیلی هوشمند نورتیکا هستم، بر پایه هوش مصنوعی — ولی با تمام
   وجود کنارتم و حرف‌هات برام مهمه.» هیچ‌وقت نگو «من انسانم».
2. تا وقتی کسی مستقیم نپرسیده، خودت را «هوش مصنوعی» یا «ربات» معرفی نکن؛ فقط با
   لحن طبیعی و گرم صحبت کن.
3. راهنمایی‌های تحصیلی، انگیزشی و مسیر آینده (رشته، دانشگاه، برنامه درسی، استرس
   امتحان، انتخاب رشته) بده؛ برای مسائل پزشکی/روان‌پزشکی جدی، محترمانه پیشنهاد بده
   با یک متخصص واقعی (روان‌شناس/مشاور حضوری) صحبت کند.
4. پاسخ‌ها کوتاه تا متوسط باشند (نه مقاله‌ای طولانی)، مگر دانش‌آموز توضیح مفصل بخواهد.

اطلاعات دانش‌آموزی که در حال گفت‌وگو با او هستی:
{student_context}
"""


def _build_student_context(user: models.User) -> str:
    parts = []
    if user.full_name:
        parts.append(f"نام: {user.full_name}")
    if user.grade:
        parts.append(f"پایه تحصیلی: {user.grade}")
    if user.field:
        parts.append(f"رشته: {user.field}")
    if user.target_major:
        parts.append(f"رشته مورد علاقه/هدف: {user.target_major}")
    if user.target_university:
        parts.append(f"دانشگاه هدف: {user.target_university}")
    return "\n".join(parts) if parts else "اطلاعاتی ثبت نشده."


def _fallback_reply(user_message: str) -> str:
    return (
        "ممنون که این موضوع رو با من در میون گذاشتی. الان امکان اتصال به سرویس هوش "
        "مصنوعی برقرار نیست، ولی پیشنهاد می‌کنم فعلاً با یکی از معلم‌ها یا مشاور "
        "مدرسه‌ات هم صحبت کنی، و کمی بعد دوباره اینجا برگرد تا با هم موضوع رو کامل "
        "بررسی کنیم."
    )


@router.get("/history/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db)):
    msgs = (
        db.query(models.ConsultationMessage)
        .filter(models.ConsultationMessage.user_id == user_id)
        .order_by(models.ConsultationMessage.created_at.asc())
        .all()
    )
    return {"items": [{"role": m.role, "content": m.content} for m in msgs]}


@router.post("/send")
def send_message(payload: schemas.ConsultationSend, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    text = (payload.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="لطفاً پیامت رو بنویس.")

    db.add(models.ConsultationMessage(user_id=user.id, role="user", content=text))
    db.commit()

    prior = (
        db.query(models.ConsultationMessage)
        .filter(models.ConsultationMessage.user_id == user.id)
        .order_by(models.ConsultationMessage.created_at.desc())
        .limit(HISTORY_LIMIT)
        .all()
    )
    prior.reverse()
    history = [{"role": m.role, "text": m.content} for m in prior]

    system_instruction = SYSTEM_INSTRUCTION_TEMPLATE.format(
        student_context=_build_student_context(user)
    )
    reply = ai_client.ask_ai_conversation(history, system_instruction=system_instruction)
    if not reply:
        reply = _fallback_reply(text)

    db.add(models.ConsultationMessage(user_id=user.id, role="assistant", content=reply))
    db.commit()

    return {"reply": reply}
