import os
import json
import random
from curriculum import get_subjects, get_weight_for_subject, build_weighted_rotation
import ai_client

PLAN_DAYS = {
    "week": 7,
    "month": 30,
    "six_month": 182,
    "year": 365,
}

PLAN_DETAIL_LEVEL = {
    "week": "ساده",
    "month": "متوسط",
    "six_month": "پیشرفته",
    "year": "بسیار پیشرفته",
}


def _build_weighted_subjects(grade, field, target_major, custom_lessons):
    subjects = list(get_subjects(grade, field))
    for lesson in (custom_lessons or []):
        subjects.append({"name": lesson.get("name") if isinstance(lesson, dict) else lesson.name,
                          "topics": lesson.get("topics", []) if isinstance(lesson, dict) else (lesson.topics or [])})

    weighted = []
    for s in subjects:
        w = get_weight_for_subject(s["name"], target_major or "")
        weighted.append({"name": s["name"], "topics": s.get("topics", []), "weight": w})
    return weighted


def _rule_based_plan(user, plan_type, custom_lessons):
    grade, field = user.grade, user.field
    subjects = _build_weighted_subjects(grade, field, user.target_major, custom_lessons)
    if not subjects:
        subjects = [{"name": "مرور عمومی", "topics": [], "weight": 1.0}]

    total_days = PLAN_DAYS.get(plan_type, 7)
    daily_hours = user.daily_hours or 2.0

    # مرتب‌سازی بر اساس وزن (اولویت رشته هدف)
    subjects_sorted = sorted(subjects, key=lambda x: x["weight"], reverse=True)

    schedule = []
    topic_cursor = {s["name"]: 0 for s in subjects}
    pool_all = subjects_sorted if subjects_sorted else subjects
    rotation = build_weighted_rotation(pool_all)
    rotation_idx = 0

    review_every = 7 if plan_type in ("week", "month") else 6
    mock_exam_every = None
    if plan_type == "six_month":
        mock_exam_every = 14
    elif plan_type == "year":
        mock_exam_every = 10

    day_num = 1
    while day_num <= total_days:
        if mock_exam_every and day_num % mock_exam_every == 0:
            schedule.append({
                "day": day_num,
                "type": "آزمون جامع شبیه‌ساز کنکور",
                "items": [{"subject": "آزمون ترکیبی", "focus": "مرور و جمع‌بندی کل مباحث خوانده‌شده",
                           "minutes": int(daily_hours * 60)}],
            })
            day_num += 1
            continue

        if day_num % review_every == 0:
            top_subjects = subjects_sorted[:3] if len(subjects_sorted) >= 3 else subjects_sorted
            schedule.append({
                "day": day_num,
                "type": "مرور و تثبیت",
                "items": [{"subject": s["name"], "focus": "مرور نکات کلیدی و حل تست", "minutes": int(daily_hours * 60 / max(len(top_subjects), 1))} for s in top_subjects],
            })
            day_num += 1
            continue

        # تعداد درس در هر روز بر اساس سطح جزئیات و ساعت مطالعه روزانه
        subjects_per_day = max(1, min(len(pool_all), round(daily_hours), 4))
        chosen_subjects = []
        seen_today = set()
        steps_tried = 0
        while len(chosen_subjects) < subjects_per_day and steps_tried < len(rotation) * 2:
            s = rotation[rotation_idx % len(rotation)]
            rotation_idx += 1
            steps_tried += 1
            if s["name"] not in seen_today or len(pool_all) < subjects_per_day:
                chosen_subjects.append(s)
                seen_today.add(s["name"])

        weight_sum = sum(s["weight"] for s in chosen_subjects) or 1.0
        total_minutes = int(daily_hours * 60)
        chosen = []
        for s in chosen_subjects:
            topic_list = s.get("topics") or ["مرور کلی درس"]
            idx = topic_cursor[s["name"]] % len(topic_list)
            topic_cursor[s["name"]] += 1
            minutes = max(15, int(total_minutes * (s["weight"] / weight_sum)))
            chosen.append({
                "subject": s["name"],
                "focus": topic_list[idx],
                "minutes": minutes,
            })

        schedule.append({"day": day_num, "type": "مطالعه", "items": chosen})
        day_num += 1

    return {
        "plan_type": plan_type,
        "detail_level": PLAN_DETAIL_LEVEL.get(plan_type, "ساده"),
        "grade": grade,
        "field": field,
        "target_major": user.target_major,
        "target_university": user.target_university,
        "daily_hours": daily_hours,
        "total_days": total_days,
        "engine": "rule_based",
        "schedule": schedule,
    }


def _try_real_ai_plan(user, plan_type, custom_lessons, base_plan):
    """در صورت وجود GEMINI_API_KEY، از مدل هوش مصنوعی رایگان Gemini برای اصلاح و
    غنی‌سازی خلاصه و توصیه‌های برنامه استفاده می‌شود. در غیر این‌صورت فقط
    خروجی موتور قانون‌محور بازگردانده می‌شود."""
    if not ai_client.has_ai_key():
        return base_plan

    prompt = (
        "شما یک مشاور تحصیلی خبره ایرانی هستید. بر اساس این اطلاعات دانش‌آموز:\n"
        f"پایه: {user.grade}, رشته: {user.field}, رشته هدف دانشگاهی: {user.target_major}, "
        f"دانشگاه هدف: {user.target_university}, ساعت مطالعه روزانه: {user.daily_hours}\n"
        "یک پاراگراف کوتاه (حداکثر ۴ خط) با لحن انگیزشی و راهکارهای کلیدی مطالعه "
        "متناسب با این رشته هدف بنویس. فقط متن فارسی خروجی بده، بدون مقدمه اضافه."
    )
    advice_text = ai_client.ask_ai(prompt, max_tokens=400)
    if advice_text:
        base_plan["ai_advice"] = advice_text
        base_plan["engine"] = "gemini_ai"
    else:
        base_plan["ai_advice"] = None
    return base_plan


def generate_plan(user, plan_type="week", custom_lessons=None):
    base_plan = _rule_based_plan(user, plan_type, custom_lessons)
    final_plan = _try_real_ai_plan(user, plan_type, custom_lessons, base_plan)
    if not final_plan.get("ai_advice"):
        final_plan["ai_advice"] = _default_advice(user)
    return final_plan


def _default_advice(user):
    tips = [
        f"با توجه به هدف تو برای «{user.target_major or 'موفقیت در کنکور'}»، تمرکز روی دروس تخصصی رشته‌ات کلید موفقیته.",
        "هر روز چند تست از درس‌های قبلی حل کن تا مطالب فراموش نشه.",
        "بین ساعات مطالعه، استراحت کوتاه فراموش نشه؛ مغز هم به نور نیاز داره!",
    ]
    return random.choice(tips)
