"""
داده‌های مدیریتی پنل ادمین: مشاهده و مدیریت تیکت‌های پشتیبانی و مشاهده لیست
کاربران ثبت‌نامی. تمام مسیرهای این فایل فقط برای ادمین لاگین‌شده در دسترس‌اند.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from admin_auth import require_admin
from database import get_db
from support_router import get_or_create_contact_info

router = APIRouter(
    prefix="/api/admin-data",
    tags=["admin-data"],
    dependencies=[Depends(require_admin)],
)


@router.get("/tickets")
def list_tickets(db: Session = Depends(get_db)):
    tickets = db.query(models.SupportTicket).order_by(models.SupportTicket.created_at.desc()).all()
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "phone": t.phone,
                "subject": t.subject,
                "message": t.message,
                "status": t.status,
            }
            for t in tickets
        ]
    }


@router.put("/tickets/{ticket_id}")
def update_ticket_status(ticket_id: int, payload: schemas.TicketStatusUpdate, db: Session = Depends(get_db)):
    ticket = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="تیکت پیدا نشد.")
    ticket.status = payload.status
    db.commit()
    return {"message": "وضعیت تیکت بروزرسانی شد."}


@router.delete("/tickets/{ticket_id}")
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="تیکت پیدا نشد.")
    db.delete(ticket)
    db.commit()
    return {"message": "تیکت حذف شد."}


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return {
        "items": [
            {
                "id": u.id,
                "full_name": u.full_name,
                "phone": u.phone,
                "email": u.email,
                "field": u.field,
                "grade": u.grade,
                "target_major": u.target_major,
            }
            for u in users
        ]
    }


@router.get("/consultations")
def list_consultations(db: Session = Depends(get_db)):
    """لیست دانش‌آموزانی که با «مشاوره تحصیلی هوشمند نورتیکا» گفت‌وگو داشته‌اند،
    به همراه تعداد پیام و آخرین پیام، برای مرور از پنل ادمین."""
    rows = (
        db.query(models.ConsultationMessage)
        .order_by(models.ConsultationMessage.created_at.asc())
        .all()
    )
    by_user = {}
    for m in rows:
        entry = by_user.setdefault(m.user_id, {"count": 0, "last": None, "last_at": None})
        entry["count"] += 1
        entry["last"] = m.content
        entry["last_at"] = m.created_at

    if not by_user:
        return {"items": []}

    users = db.query(models.User).filter(models.User.id.in_(by_user.keys())).all()
    users_by_id = {u.id: u for u in users}

    items = []
    for user_id, data in by_user.items():
        user = users_by_id.get(user_id)
        items.append({
            "user_id": user_id,
            "full_name": user.full_name if user else "کاربر حذف‌شده",
            "message_count": data["count"],
            "last_message": (data["last"] or "")[:120],
        })
    items.sort(key=lambda x: x["message_count"], reverse=True)
    return {"items": items}


@router.get("/consultations/{user_id}")
def get_consultation_transcript(user_id: int, db: Session = Depends(get_db)):
    msgs = (
        db.query(models.ConsultationMessage)
        .filter(models.ConsultationMessage.user_id == user_id)
        .order_by(models.ConsultationMessage.created_at.asc())
        .all()
    )
    return {"items": [{"role": m.role, "content": m.content} for m in msgs]}


# ---------------------------------------------------------------------
# اطلاعات تماس پشتیبانی (آدرس محل کار، کانال تلگرام/بله، تلفن شرکت)
# ---------------------------------------------------------------------

@router.get("/contact-info")
def admin_get_contact_info(db: Session = Depends(get_db)):
    info = get_or_create_contact_info(db)
    return {
        "office_address": info.office_address or "",
        "telegram_channel": info.telegram_channel or "",
        "bale_channel": info.bale_channel or "",
        "instagram_channel": info.instagram_channel or "",
        "company_phone": info.company_phone or "",
    }


@router.put("/contact-info")
def admin_update_contact_info(payload: schemas.ContactInfoUpdate, db: Session = Depends(get_db)):
    info = get_or_create_contact_info(db)
    info.office_address = payload.office_address or ""
    info.telegram_channel = payload.telegram_channel or ""
    info.bale_channel = payload.bale_channel or ""
    info.instagram_channel = payload.instagram_channel or ""
    info.company_phone = payload.company_phone or ""
    db.commit()
    return {"message": "اطلاعات تماس بروزرسانی شد."}


@router.delete("/contact-info/{field_name}")
def admin_clear_contact_info_field(field_name: str, db: Session = Depends(get_db)):
    allowed = {"office_address", "telegram_channel", "bale_channel", "instagram_channel", "company_phone"}
    if field_name not in allowed:
        raise HTTPException(status_code=400, detail="نام فیلد نامعتبر است.")
    info = get_or_create_contact_info(db)
    setattr(info, field_name, "")
    db.commit()
    return {"message": "فیلد مورد نظر پاک شد."}
