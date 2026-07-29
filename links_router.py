"""
مدیریت لینک‌های دلخواه سایت (مثل شبکه‌های اجتماعی یا لینک‌های سفارشی) از
طریق پنل ادمین. مسیر GET عمومی است تا در آینده بتوان این لینک‌ها را در هر
جای سایت (مثلاً فوتر) نمایش داد؛ مسیرهای ساخت/ویرایش/حذف فقط برای ادمین.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from admin_auth import require_admin
from database import get_db

router = APIRouter(prefix="/api/links", tags=["links"])


@router.get("")
def list_links(db: Session = Depends(get_db)):
    items = (
        db.query(models.SiteLink)
        .order_by(models.SiteLink.position.asc(), models.SiteLink.id.asc())
        .all()
    )
    return {
        "items": [
            {"id": l.id, "title": l.title, "url": l.url, "position": l.position}
            for l in items
        ]
    }


@router.post("", dependencies=[Depends(require_admin)])
def create_link(payload: schemas.LinkCreate, db: Session = Depends(get_db)):
    title = payload.title.strip()
    url = payload.url.strip()
    if not title or not url:
        raise HTTPException(status_code=400, detail="عنوان و آدرس لینک نمی‌تواند خالی باشد.")

    link = models.SiteLink(title=title, url=url, position=payload.position or 0)
    db.add(link)
    db.commit()
    db.refresh(link)
    return {"id": link.id, "message": "لینک با موفقیت اضافه شد."}


@router.put("/{link_id}", dependencies=[Depends(require_admin)])
def update_link(link_id: int, payload: schemas.LinkCreate, db: Session = Depends(get_db)):
    title = payload.title.strip()
    url = payload.url.strip()
    if not title or not url:
        raise HTTPException(status_code=400, detail="عنوان و آدرس لینک نمی‌تواند خالی باشد.")

    link = db.query(models.SiteLink).filter(models.SiteLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="لینک پیدا نشد.")

    link.title = title
    link.url = url
    link.position = payload.position or 0
    db.commit()
    return {"message": "لینک ویرایش شد."}


@router.delete("/{link_id}", dependencies=[Depends(require_admin)])
def delete_link(link_id: int, db: Session = Depends(get_db)):
    link = db.query(models.SiteLink).filter(models.SiteLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="لینک پیدا نشد.")
    db.delete(link)
    db.commit()
    return {"message": "لینک حذف شد."}
