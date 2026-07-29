from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from ai_quiz import generate_quiz, analyze_wrong_answers, analyze_essay_answers

router = APIRouter(prefix="/api/exams", tags=["exams"])


@router.post("/generate")
def create_quiz(payload: schemas.QuizRequest, db: Session = Depends(get_db)):
    quiz = generate_quiz(
        db,
        payload.subject,
        payload.lesson,
        payload.grade,
        payload.question_count,
        payload.difficulty,
        payload.question_type,
    )
    return {"quiz": quiz}


@router.post("/submit")
def submit_quiz(payload: schemas.QuizSubmit, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    if len(payload.answers) != len(payload.correct_answers):
        raise HTTPException(status_code=400, detail="داده‌های پاسخ نامعتبر است.")

    correct = sum(
        1 for a, c in zip(payload.answers, payload.correct_answers) if a == c
    )
    total = len(payload.correct_answers)
    score_percent = round((correct / total) * 100, 1) if total else 0.0

    result = models.ExamResult(
        user_id=payload.user_id,
        subject=payload.subject,
        lesson=payload.lesson,
        question_count=total,
        correct_count=correct,
        score_percent=score_percent,
    )
    db.add(result)
    db.commit()

    # تحلیل هوشمند سوالات غلط برای این‌که دانش‌آموز اشتباهش را بفهمد و اصلاح کند
    wrong_items = []
    if payload.questions:
        for i, (a, c) in enumerate(zip(payload.answers, payload.correct_answers)):
            if a != c and i < len(payload.questions):
                q = payload.questions[i]
                wrong_items.append({
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "correct_index": c,
                    "user_index": a,
                })
    wrong_analysis = analyze_wrong_answers(payload.subject, payload.grade or "", wrong_items)

    return {
        "correct_count": correct,
        "total": total,
        "score_percent": score_percent,
        "message": "کارنامه آزمون شما ثبت شد.",
        "wrong_analysis": wrong_analysis,
    }


@router.post("/essay/submit")
def submit_essay(payload: schemas.EssaySubmit, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    answers = [a.dict() for a in payload.answers]
    analysis = analyze_essay_answers(payload.subject, payload.grade or "", answers)

    avg_score = 0.0
    if analysis:
        scores = [a.get("score_percent", 0) for a in analysis]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    result = models.ExamResult(
        user_id=payload.user_id,
        subject=payload.subject,
        lesson=payload.subject,
        question_count=len(answers),
        correct_count=int(round(avg_score / 100 * len(answers))) if answers else 0,
        score_percent=avg_score,
    )
    db.add(result)
    db.commit()

    return {
        "message": "پاسخ‌های تشریحی شما ثبت و تحلیل شد.",
        "average_score_percent": avg_score,
        "analysis": analysis,
    }
