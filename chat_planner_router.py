from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from ai_chat_planner import generate_chat_plan
from pdf_export import build_plan_pdf

router = APIRouter(prefix="/api/chat-planner", tags=["chat-planner"])


@router.post("/generate")
def create_chat_plan(payload: schemas.ChatPlanRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="لطفاً درخواست خود را بنویس.")

    plan_content = generate_chat_plan(
        user,
        payload.message,
        days_of_week=payload.days_of_week or None,
        start_date_str=payload.start_date or None,
        end_date_str=payload.end_date or None,
    )

    plan_record = models.StudyPlan(
        user_id=user.id, plan_type="chat", content=plan_content
    )
    db.add(plan_record)
    db.commit()
    db.refresh(plan_record)

    return {"plan_id": plan_record.id, "plan": plan_content}


@router.post("/pdf")
def export_plan_pdf(payload: schemas.ChatPlanPdfRequest):
    pdf_bytes = build_plan_pdf(payload.plan)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=noortika-plan.pdf"},
    )
