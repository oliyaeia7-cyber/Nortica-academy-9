import os
import json as _json
from datetime import datetime, timedelta

from curriculum import get_subjects, get_weight_for_subject, build_weighted_rotation
import ai_client

# نگاشت weekday پایتون (دوشنبه=0) به نام روز هفته فارسی
PY_WEEKDAY_TO_FA = {
    0: "دوشنبه",
    1: "سه‌شنبه",
    2: "چهارشنبه",
    3: "پنجشنبه",
    4: "جمعه",
    5: "شنبه",
    6: "یکشنبه",
}

FIELD_KEYS = ["عمومی", "ریاضی فیزیک", "علوم تجربی", "علوم انسانی", "فنی حرفه‌ای"]

# ترتیب مهمه: چون "دهم" زیررشته‌ی متنی "یازدهم" و "دوازدهم" هم هست،
# باید از پایه‌های خاص‌تر به کلی‌تر بررسی کنیم تا اشتباه تشخیص داده نشه.
GRADE_DETECTION_ORDER = ["دوازدهم", "یازدهم", "دهم", "نهم", "هشتم", "هفتم"]

FIELD_ALIASES = {
    "ریاضی فیزیک": ["ریاضی فیزیک", "ریاضی‌فیزیک", "ریاضی و فیزیک"],
    "علوم تجربی": ["علوم تجربی", "تجربی"],
    "علوم انسانی": ["علوم انسانی", "انسانی"],
    "فنی حرفه‌ای": ["فنی حرفه‌ای", "فنی‌حرفه‌ای", "فنی و حرفه‌ای", "فنی حرفه ای", "فنی‌حرفه ای"],
    "عمومی": ["عمومی"],
}

# اگر کاربر با این عبارت‌ها بخواد، یعنی همه‌ی دروس با هم (نه فقط یک درس خاص)
FULL_PLAN_KEYWORDS = [
    "همه دروس", "همه‌ی دروس", "همه ی دروس", "همه درسا", "همه چیز",
    "تمام دروس", "کامل", "همه با هم", "همه فصل", "همه‌ی کتاب", "همه کتاب‌ها",
]

# ریشه‌ی نام دروس، برای وقتی کاربر فقط بخشی از نام درس رو می‌نویسه
# (مثلاً «فارسی» به‌جای «ادبیات فارسی (۲)»)
SUBJECT_ROOT_KEYWORDS = [
    "ریاضی", "فیزیک", "شیمی", "زیست", "فارسی", "ادبیات", "عربی", "دین",
    "انگلیسی", "تاریخ", "جغرافیا", "جامعه", "فلسفه", "روان", "اقتصاد",
    "منطق", "هندسه", "حسابان", "آمار", "گسسته", "کارگاه", "دانش فنی", "زمین",
]


def _all_user_subjects(grade, field):
    subjects = list(get_subjects(grade, field))
    if not subjects:
        # اگر رشته دقیق پیدا نشد، در همه گروه‌های همان پایه بگرد
        for fk in FIELD_KEYS:
            subjects = list(get_subjects(grade, fk))
            if subjects:
                break
    return subjects


def detect_requested_grade(message, fallback_grade):
    """پایه‌ای که کاربر توی متن آزادش نوشته رو پیدا می‌کنه؛ اگر چیزی پیدا نشد،
    پایه ثبت‌نامی کاربر (fallback_grade) رو برمی‌گردونه."""
    msg = (message or "")
    for g in GRADE_DETECTION_ORDER:
        if g in msg:
            return g
    return fallback_grade


def detect_requested_field(message, grade, fallback_field):
    """رشته‌ای که کاربر توی متن آزادش نوشته رو پیدا می‌کنه (فقط اگر برای همون
    پایه معتبر باشه)؛ در غیر این‌صورت رشته ثبت‌نامی کاربر رو برمی‌گردونه."""
    msg = (message or "")
    for field_key, aliases in FIELD_ALIASES.items():
        if any(alias in msg for alias in aliases):
            if get_subjects(grade, field_key):
                return field_key
    return fallback_field


def _strip_grade_field_terms(message, requested_grade):
    """قبل از تشخیص درس مدنظر، عبارت‌های مربوط به پایه/رشته (مثل «ریاضی فیزیک»)
    را از متن حذف می‌کنیم تا کلمه‌ی «فیزیک» توی نام رشته، اشتباهی به‌عنوان
    درخواست تک‌درسی «فیزیک» شناسایی نشه."""
    text = message or ""
    if requested_grade and requested_grade in text:
        text = text.replace(requested_grade, " ")
    for aliases in FIELD_ALIASES.values():
        for alias in aliases:
            if alias in text:
                text = text.replace(alias, " ")
    return text


def _wants_full_plan(message):
    msg = (message or "")
    return any(kw in msg for kw in FULL_PLAN_KEYWORDS)


def _detect_focus_subjects(message, grade, field):
    """از روی متن آزاد کاربر، درس(های) مدنظر را پیدا می‌کند.
    - اگر کاربر صراحتاً گفته «همه/کامل»، همه‌ی دروس برگردانده می‌شود.
    - اگر یک یا چند درس مشخص خواسته (مثلاً «فقط فارسی»)، فقط همان‌ها برمی‌گردد
      و با درس‌های دیگر قاطی نمی‌شود.
    - اگر هیچ درسی به‌صراحت مشخص نشده، همه‌ی دروس برگردانده می‌شود (رفتار پیش‌فرض)."""
    all_subjects = _all_user_subjects(grade, field)
    if not all_subjects:
        return []

    if _wants_full_plan(message):
        return all_subjects

    msg = (message or "").strip()
    found = []
    found_names = set()

    # ۱) تطبیق دقیق با نام کامل درس (بیشترین دقت)
    for s in all_subjects:
        base_name = s["name"].split(" (")[0].strip()
        if base_name and base_name in msg and s["name"] not in found_names:
            found.append(s)
            found_names.add(s["name"])

    # ۲) اگر با نام کامل چیزی پیدا نشد، از روی ریشه‌ی نام درس بگرد
    if not found:
        for s in all_subjects:
            base_name = s["name"].split(" (")[0].strip()
            for root in SUBJECT_ROOT_KEYWORDS:
                if root in base_name and root in msg:
                    found.append(s)
                    found_names.add(s["name"])
                    break

    return found or all_subjects


def _default_analysis(user, message, focus_subjects, requested_grade, grade_overridden):
    names = "، ".join(s["name"] for s in focus_subjects[:4]) or "دروس اصلی"
    override_note = ""
    if grade_overridden:
        override_note = (
            f" (طبق درخواست خودت، این برنامه برای پایه {requested_grade} چیده شده، "
            f"نه پایه ثبت‌نامت.)"
        )
    return (
        f"بر اساس درخواستت، یک برنامه مطالعاتی برای {names} با توجه به پایه {requested_grade}{override_note} "
        f"و ساعت مطالعه روزانه {user.daily_hours or 2} ساعت طراحی کردم. برنامه به‌گونه‌ای چیده شده که "
        "هم مباحث جدید پوشش داده بشه و هم زمان کافی برای مرور و حل تست در نظر گرفته بشه."
    )


def _default_subject_distribution(focus_subjects):
    if not focus_subjects:
        return [{"subject": "مرور عمومی", "percent": 100}]
    equal = round(100 / len(focus_subjects))
    dist = [{"subject": s["name"], "percent": equal} for s in focus_subjects]
    diff = 100 - sum(d["percent"] for d in dist)
    if dist:
        dist[0]["percent"] += diff
    return dist


def _default_growth_table(weeks_count):
    weeks_count = max(1, weeks_count)
    table = []
    start = 30
    step = max(5, int(50 / weeks_count))
    for w in range(1, weeks_count + 1):
        table.append({
            "week": w,
            "expected_mastery_percent": min(95, start + step * (w - 1)),
            "note": "مرور، تمرین و رفع اشکال" if w > 1 else "شروع و آشنایی با مباحث",
        })
    return table


def _try_ai_chat_analysis(user, message, focus_subjects, weeks_count, requested_grade, requested_field, grade_overridden):
    fallback = {
        "analysis": _default_analysis(user, message, focus_subjects, requested_grade, grade_overridden),
        "subject_distribution": _default_subject_distribution(focus_subjects),
        "growth_table": _default_growth_table(weeks_count),
        "engine": "rule_based",
    }
    if not ai_client.has_ai_key():
        return fallback

    override_line = (
        f"توجه: کاربر توی همین پیام صراحتاً پایه/رشته دیگری غیر از پایه ثبت‌نامش خواسته؛ "
        f"حتماً برای پایه {requested_grade} و رشته {requested_field} برنامه بچین، نه پایه ثبت‌نام.\n"
        if grade_overridden else ""
    )
    prompt = (
        "شما دستیار هوشمند برنامه‌ریزی تحصیلی نورتیکا هستی و مثل یک چت هوشمند به دانش‌آموز پاسخ می‌دهی.\n"
        f"مشخصات ثبت‌نامی دانش‌آموز: پایه {user.grade}، رشته {user.field}، رشته هدف دانشگاهی {user.target_major or 'مشخص نشده'}، "
        f"ساعت مطالعه روزانه {user.daily_hours or 2} ساعت.\n"
        f"پایه و رشته‌ای که باید برای همین برنامه در نظر بگیری: پایه {requested_grade}، رشته {requested_field}.\n"
        f"{override_line}"
        f"درخواست دانش‌آموز (متن آزاد): «{message}»\n"
        f"دروس شناسایی‌شده مرتبط با درخواست: {', '.join(s['name'] for s in focus_subjects) or 'نامشخص'}\n"
        "این لیست دروس، محدوده‌ی دقیق برنامه است؛ فقط همین‌ها را در برنامه بیاور و درس دیگری اضافه نکن، "
        "مگر این‌که این لیست شامل همه‌ی دروس آن پایه باشد.\n"
        f"بازه برنامه تقریباً {weeks_count} هفته است.\n\n"
        "خروجی را فقط به‌صورت JSON خالص (بدون Markdown و بدون متن اضافه) با این ساختار دقیق بده:\n"
        '{"analysis": "یک پاراگراف تحلیلی و انگیزشی درباره این برنامه، مثل پاسخ یک مشاور در چت",'
        ' "subject_distribution": [{"subject": "نام درس", "percent": عدد}],'
        ' "growth_table": [{"week": 1, "expected_mastery_percent": عدد, "note": "توضیح کوتاه پیشرفت آن هفته"}]}'
    )
    parsed = ai_client.ask_ai_json(prompt, max_tokens=1800)
    if not parsed:
        return fallback

    parsed["engine"] = "gemini_ai"
    if not parsed.get("subject_distribution"):
        parsed["subject_distribution"] = fallback["subject_distribution"]
    if not parsed.get("growth_table"):
        parsed["growth_table"] = fallback["growth_table"]
    return parsed


def _iter_dates(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)


def _build_dated_schedule(user, focus_subjects, days_of_week, start_date, end_date):
    subjects = focus_subjects or [{"name": "مرور عمومی", "topics": []}]
    weighted = []
    for s in subjects:
        w = get_weight_for_subject(s["name"], user.target_major or "")
        weighted.append({"name": s["name"], "topics": s.get("topics") or ["مرور کلی درس"], "weight": w})
    weighted.sort(key=lambda x: x["weight"], reverse=True)

    # چرخه‌ی وزن‌دار: دروس مهم‌تر برای رشته هدف دانشگاهی، دفعات بیشتری در برنامه تکرار می‌شوند
    rotation = build_weighted_rotation(weighted)

    daily_hours = user.daily_hours or 2.0
    topic_cursor = {s["name"]: 0 for s in weighted}

    schedule = []
    day_counter = 0
    rotation_idx = 0
    for d in _iter_dates(start_date, end_date):
        fa_day = PY_WEEKDAY_TO_FA[d.weekday()]
        if days_of_week and fa_day not in days_of_week:
            continue
        day_counter += 1
        # تعداد درس هر روز هم به تعداد دروس و هم به ساعت مطالعه روزانه بستگی داره
        subjects_per_day = max(1, min(len(weighted), round(daily_hours), 4)) or 1
        chosen_subjects = []
        seen_today = set()
        steps_tried = 0
        while len(chosen_subjects) < subjects_per_day and steps_tried < len(rotation) * 2:
            s = rotation[rotation_idx % len(rotation)]
            rotation_idx += 1
            steps_tried += 1
            if s["name"] not in seen_today or len(weighted) < subjects_per_day:
                chosen_subjects.append(s)
                seen_today.add(s["name"])

        weight_sum = sum(s["weight"] for s in chosen_subjects) or 1.0
        total_minutes = int(daily_hours * 60)
        chosen = []
        for s in chosen_subjects:
            topic_list = s["topics"] or ["مرور کلی درس"]
            idx = topic_cursor[s["name"]] % len(topic_list)
            topic_cursor[s["name"]] += 1
            minutes = max(15, int(total_minutes * (s["weight"] / weight_sum)))
            chosen.append({
                "subject": s["name"],
                "focus": topic_list[idx],
                "minutes": minutes,
            })
        schedule.append({
            "date": d.strftime("%Y-%m-%d"),
            "day_name": fa_day,
            "type": "آزمون و جمع‌بندی" if day_counter % 7 == 0 else "مطالعه",
            "items": chosen,
        })
    return schedule


def generate_chat_plan(user, message, days_of_week=None, start_date_str=None, end_date_str=None):
    # اگر کاربر توی متن آزادش پایه/رشته دیگری (غیر از پایه ثبت‌نامش) خواسته باشه،
    # همون رو در نظر می‌گیریم، نه پایه/رشته ثبت‌نام.
    requested_grade = detect_requested_grade(message, user.grade)
    requested_field = detect_requested_field(message, requested_grade, user.field)
    grade_overridden = requested_grade != user.grade or requested_field != user.field

    subject_scan_text = _strip_grade_field_terms(message, requested_grade)
    focus_subjects = _detect_focus_subjects(subject_scan_text, requested_grade, requested_field)

    today = datetime.utcnow().date()
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    else:
        start_date = today
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    else:
        end_date = start_date + timedelta(days=6)

    if end_date < start_date:
        start_date, end_date = end_date, start_date

    total_span_days = (end_date - start_date).days + 1
    weeks_count = max(1, round(total_span_days / 7))

    ai_part = _try_ai_chat_analysis(
        user, message, focus_subjects, weeks_count,
        requested_grade, requested_field, grade_overridden,
    )
    schedule = _build_dated_schedule(user, focus_subjects, days_of_week, start_date, end_date)

    return {
        "message": message,
        "grade": requested_grade,
        "field": requested_field,
        "grade_overridden": grade_overridden,
        "focus_subjects": [s["name"] for s in focus_subjects],
        "days_of_week": days_of_week or [],
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "analysis": ai_part.get("analysis", ""),
        "subject_distribution": ai_part.get("subject_distribution", []),
        "growth_table": ai_part.get("growth_table", []),
        "engine": ai_part.get("engine", "rule_based"),
        "schedule": schedule,
    }
