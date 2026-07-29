from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from ai_planner import generate_plan
from curriculum import get_subjects

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("/subjects")
def list_subjects(grade: str, field: str):
    return {"subjects": get_subjects(grade, field)}


@router.post("/generate")
def create_plan(payload: schemas.PlanRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    plan_content = generate_plan(user, payload.plan_type, payload.custom_lessons)

    plan_record = models.StudyPlan(
        user_id=user.id, plan_type=payload.plan_type, content=plan_content
    )
    db.add(plan_record)
    db.commit()
    db.refresh(plan_record)

    return {"plan_id": plan_record.id, "plan": plan_content}


@router.get("/latest/{user_id}")
def latest_plan(user_id: int, db: Session = Depends(get_db)):
    plan = (
        db.query(models.StudyPlan)
        .filter(models.StudyPlan.user_id == user_id)
        .order_by(models.StudyPlan.id.desc())
        .first()
    )
    if not plan:
        return {"plan": None}
    return {"plan_id": plan.id, "plan": plan.content}
