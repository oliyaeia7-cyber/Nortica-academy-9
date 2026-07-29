from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from admin_auth import require_admin
import models, schemas

router = APIRouter(prefix="/api/subscription", tags=["subscription"])

# مقادیر پیش‌فرض پلن‌ها — فقط برای seed اولیه دیتابیس استفاده می‌شوند.
# بعد از seed، منبع اصلی قیمت‌ها جدول pricing_plans است و از پنل ادمین
# (تب «💰 قیمت‌گذاری») قابل ویرایش است.
DEFAULT_PLANS = [
    {"plan_key": "free_week", "title": "برنامه هفتگی", "duration": "week",
     "description": "برنامه‌ای ساده و جزئی برای یک هفته", "price": 0, "price_label": "رایگان", "position": 1},
    {"plan_key": "month", "title": "برنامه یک ماهه", "duration": "month",
     "description": "برنامه دقیق‌تر با جزئیات بیشتر", "price": 500000, "price_label": "۵۰۰,۰۰۰ تومان", "position": 2},
    {"plan_key": "six_month", "title": "برنامه شش ماهه", "duration": "six_month",
     "description": "برنامه‌ای عالی و کامل با موتور هوش مصنوعی دقیق‌تر", "price": 1000000, "price_label": "۱,۰۰۰,۰۰۰ تومان", "position": 3},
    {"plan_key": "year", "title": "برنامه یک ساله", "duration": "year",
     "description": "برنامه بسیار قدرتمند همراه با پنل اختصاصی", "price": 2000000, "price_label": "۲,۰۰۰,۰۰۰ تومان", "position": 4},
]


def seed_pricing_plans(db: Session):
    """اگر جدول پلن‌ها خالی بود، پلن‌های پیش‌فرض را اضافه می‌کند (idempotent)."""
    if db.query(models.PricingPlan).count() > 0:
        return
    for p in DEFAULT_PLANS:
        db.add(models.PricingPlan(**p))
    db.commit()


def _serialize_plan(p: models.PricingPlan) -> dict:
    return {
        "id": p.plan_key, "title": p.title, "duration": p.duration,
        "description": p.description, "price": p.price, "price_label": p.price_label,
    }


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    plans = db.query(models.PricingPlan).order_by(models.PricingPlan.position.asc()).all()
    return {"plans": [_serialize_plan(p) for p in plans]}


@router.post("/subscribe")
def subscribe(payload: schemas.SubscribeRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    plan = db.query(models.PricingPlan).filter(models.PricingPlan.plan_key == payload.plan_id).first()
    if not plan:
        raise HTTPException(status_code=400, detail="پلن نامعتبر است.")

    sub = db.query(models.Subscription).filter(models.Subscription.user_id == user.id).first()
    if not sub:
        sub = models.Subscription(user_id=user.id)
        db.add(sub)

    sub.plan_id = plan.plan_key
    sub.plan_title = plan.title
    sub.is_active = 1
    db.commit()

    return {
        "message": f"پرداخت نمادین برای «{plan.title}» با موفقیت انجام شد. (این یک تراکنش آزمایشی است و مبلغ واقعی کسر نشده است)",
        "plan": _serialize_plan(plan),
    }


@router.get("/status/{user_id}")
def subscription_status(user_id: int, db: Session = Depends(get_db)):
    sub = db.query(models.Subscription).filter(models.Subscription.user_id == user_id).first()
    if not sub:
        return {"plan_id": "free_week", "plan_title": "برنامه هفتگی"}
    return {"plan_id": sub.plan_id, "plan_title": sub.plan_title}


# ---------------------------------------------------------------------
# مدیریت پلن‌های قیمت‌گذاری از پنل ادمین
# ---------------------------------------------------------------------
@router.get("/admin/plans", dependencies=[Depends(require_admin)])
def admin_list_plans(db: Session = Depends(get_db)):
    plans = db.query(models.PricingPlan).order_by(models.PricingPlan.position.asc()).all()
    return {
        "items": [
            {
                "id": p.id, "plan_key": p.plan_key, "title": p.title, "duration": p.duration,
                "description": p.description, "price": p.price, "price_label": p.price_label,
                "position": p.position,
            }
            for p in plans
        ]
    }


@router.put("/admin/plans/{plan_id}", dependencies=[Depends(require_admin)])
def admin_update_plan(plan_id: int, payload: schemas.PricingPlanUpdate, db: Session = Depends(get_db)):
    plan = db.query(models.PricingPlan).filter(models.PricingPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="پلن پیدا نشد.")

    # اگر plan_key تغییر کرده، مطمئن شو با پلن دیگری تداخل ندارد
    if payload.plan_key != plan.plan_key:
        exists = db.query(models.PricingPlan).filter(
            models.PricingPlan.plan_key == payload.plan_key, models.PricingPlan.id != plan_id
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="این شناسه پلن قبلاً استفاده شده است.")

    plan.plan_key = payload.plan_key
    plan.title = payload.title
    plan.duration = payload.duration
    plan.description = payload.description
    plan.price = payload.price
    plan.price_label = payload.price_label
    plan.position = payload.position or 0
    db.commit()
    return {"message": "پلن با موفقیت ویرایش شد."}


@router.post("/admin/plans", dependencies=[Depends(require_admin)])
def admin_create_plan(payload: schemas.PricingPlanUpdate, db: Session = Depends(get_db)):
    exists = db.query(models.PricingPlan).filter(models.PricingPlan.plan_key == payload.plan_key).first()
    if exists:
        raise HTTPException(status_code=400, detail="این شناسه پلن قبلاً استفاده شده است.")
    plan = models.PricingPlan(
        plan_key=payload.plan_key, title=payload.title, duration=payload.duration,
        description=payload.description, price=payload.price, price_label=payload.price_label,
        position=payload.position or 0,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"id": plan.id, "message": "پلن جدید اضافه شد."}


@router.delete("/admin/plans/{plan_id}", dependencies=[Depends(require_admin)])
def admin_delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(models.PricingPlan).filter(models.PricingPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="پلن پیدا نشد.")
    db.delete(plan)
    db.commit()
    return {"message": "پلن حذف شد."}
