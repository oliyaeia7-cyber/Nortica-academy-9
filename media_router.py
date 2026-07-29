"""
کتابخانه رسانه نورتیکا.

تصاویر آپلودشده از پنل ادمین به‌صورت base64 داخل دیتابیس ذخیره می‌شوند (دقیقاً
هماهنگ با رویکرد فعلی پروژه که لوگو هم در assets.py به همین شکل نگه‌داری
می‌شود) تا نیازی به دیسک پایدار روی Render نباشد. هر تصویر یک آدرس عمومی به
شکل /media/{id} می‌گیرد که در هر جای سایت (مثلاً کاور مقالات وبلاگ) قابل
استفاده است.
"""
import base64

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

import models
from admin_auth import require_admin
from database import get_db

router = APIRouter(tags=["media"])

MAX_SIZE_BYTES = 5 * 1024 * 1024  # ۵ مگابایت
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/svg+xml",
}


@router.post("/api/media/upload", dependencies=[Depends(require_admin)])
async def upload_media(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="فقط فایل تصویری مجاز است (jpg, png, webp, gif, svg).",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="فایل خالی است.")
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="حجم فایل نباید بیشتر از ۵ مگابایت باشد.")

    asset = models.MediaAsset(
        filename=file.filename or "upload",
        content_type=file.content_type,
        data_b64=base64.b64encode(content).decode("ascii"),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {"id": asset.id, "url": f"/media/{asset.id}", "message": "تصویر با موفقیت آپلود شد."}


@router.get("/api/media", dependencies=[Depends(require_admin)])
def list_media(db: Session = Depends(get_db)):
    items = db.query(models.MediaAsset).order_by(models.MediaAsset.created_at.desc()).all()
    return {
        "items": [
            {"id": a.id, "url": f"/media/{a.id}", "filename": a.filename}
            for a in items
        ]
    }


@router.delete("/api/media/{media_id}", dependencies=[Depends(require_admin)])
def delete_media(media_id: int, db: Session = Depends(get_db)):
    asset = db.query(models.MediaAsset).filter(models.MediaAsset.id == media_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="تصویر پیدا نشد.")
    db.delete(asset)
    db.commit()
    return {"message": "تصویر حذف شد."}


@router.get("/media/{media_id}")
def serve_media(media_id: int, db: Session = Depends(get_db)):
    asset = db.query(models.MediaAsset).filter(models.MediaAsset.id == media_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="تصویر پیدا نشد.")
    content = base64.b64decode(asset.data_b64)
    return Response(
        content=content,
        media_type=asset.content_type,
        headers={"Cache-Control": "public, max-age=604800"},
    )
