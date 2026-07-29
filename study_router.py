from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas

router = APIRouter(prefix="/api/study", tags=["study"])


@router.post("/log")
def log_study(payload: schemas.StudyLogCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    log = models.StudyLog(user_id=payload.user_id, hours=payload.hours, subject=payload.subject)
    db.add(log)
    db.commit()
    return {"message": "ساعت مطالعه ثبت شد."}


@router.get("/total/{user_id}")
def total_hours(user_id: int, db: Session = Depends(get_db)):
    logs = db.query(models.StudyLog).filter(models.StudyLog.user_id == user_id).all()
    total = sum(l.hours for l in logs)
    return {"total_hours": total}
