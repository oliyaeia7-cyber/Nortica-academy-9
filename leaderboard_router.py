from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

PRIZES = {
    1: "کارت هدیه ۵۰۰ هزار تومانی + یک ماه اشتراک ویژه رایگان",
    2: "کارت هدیه ۳۰۰ هزار تومانی",
    3: "کارت هدیه ۱۵۰ هزار تومانی",
}


@router.get("")
def get_leaderboard(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    board = []

    for u in users:
        total_hours = db.query(func.coalesce(func.sum(models.StudyLog.hours), 0.0)).filter(
            models.StudyLog.user_id == u.id
        ).scalar()

        avg_score = db.query(func.coalesce(func.avg(models.ExamResult.score_percent), 0.0)).filter(
            models.ExamResult.user_id == u.id
        ).scalar()

        exam_count = db.query(func.count(models.ExamResult.id)).filter(
            models.ExamResult.user_id == u.id
        ).scalar()

        # امتیاز نهایی: ساعات مطالعه به‌عنوان معیار اصلی + امتیاز آزمون‌ها به‌عنوان ضریب کیفیت
        final_score = round(total_hours + (avg_score / 100.0) * min(exam_count, 10), 2)

        board.append({
            "user_id": u.id,
            "full_name": u.full_name,
            "field": u.field,
            "grade": u.grade,
            "total_hours": round(total_hours, 1),
            "avg_score": round(avg_score, 1),
            "exam_count": exam_count,
            "final_score": final_score,
        })

    board.sort(key=lambda x: x["final_score"], reverse=True)

    for i, entry in enumerate(board):
        rank = i + 1
        entry["rank"] = rank
        entry["prize"] = PRIZES.get(rank)

    return {"leaderboard": board}
