from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models, schemas

router = APIRouter(prefix="/api/support", tags=["support"])

# منبع واحد سوالات متداول پشتیبانی؛ هم برای API و هم برای رندر سرور-ساید و
# اسکیمای FAQPage در pages.py استفاده می‌شود تا محتوا و schema همیشه یکی باشند.
SUPPORT_FAQ = [
    {"q": "چطور برنامه درسی من ساخته می‌شود؟",
     "a": "بر اساس پایه تحصیلی، رشته و رشته هدف دانشگاهی‌ات، هوش مصنوعی نورتیکا یک برنامه اختصاصی روزانه برایت طراحی می‌کند."},
    {"q": "آیا می‌توانم درس دلخواه اضافه کنم؟",
     "a": "بله، در صفحه ساخت برنامه امکان افزودن درس یا کتاب دلخواه وجود دارد."},
    {"q": "جوایز رتبه‌بندی چگونه اهدا می‌شود؟",
     "a": "پس از هر دوره، به سه نفر برتر بر اساس ساعات مطالعه و نتایج آزمون‌ها جوایز نمادین تعلق می‌گیرد."},
    {"q": "پرداخت اشتراک چگونه است؟",
     "a": "در نسخه فعلی، پرداخت به صورت نمادین (آزمایشی) انجام می‌شود و درگاه واقعی بانکی متصل نیست."},
]


@router.post("")
def create_ticket(payload: schemas.SupportCreate, db: Session = Depends(get_db)):
    ticket = models.SupportTicket(**payload.dict())
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"ticket_id": ticket.id, "message": "پیام شما با موفقیت برای پشتیبانی نورتیکا ارسال شد."}


@router.get("/faq")
def get_faq():
    return {"faq": SUPPORT_FAQ}


def get_or_create_contact_info(db: Session) -> models.SiteContactInfo:
    info = db.query(models.SiteContactInfo).first()
    if not info:
        info = models.SiteContactInfo(
            office_address="", telegram_channel="", bale_channel="",
            instagram_channel="", company_phone="",
        )
        db.add(info)
        db.commit()
        db.refresh(info)
    return info


@router.get("/contact-info")
def get_contact_info(db: Session = Depends(get_db)):
    info = get_or_create_contact_info(db)
    return {
        "office_address": info.office_address or "",
        "telegram_channel": info.telegram_channel or "",
        "bale_channel": info.bale_channel or "",
        "instagram_channel": info.instagram_channel or "",
        "company_phone": info.company_phone or "",
    }
