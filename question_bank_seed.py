"""
سوالات اولیه (seed) برای بانک سوالات آزمون — فقط برای این‌که بانک سوالات از
ابتدا کاملاً خالی نباشد و بشود نحوه کارکرد را دید. این سوالات source='manual'
دارند (یعنی در آزمون‌ها اولویت دارند). تعداد این سوالات کم است؛ برای پوشش
واقعی «همه فصل‌های همه کتاب‌ها»، باید به‌مرور از پنل ادمین (بخش «بانک سوالات
آزمون») سوالات بیشتری اضافه شود — موتور آزمون تا وقتی سوال دستی کافی نباشد،
از تولید خودکار مبتنی بر سرفصل کتاب درسی به‌عنوان مکمل استفاده می‌کند.
"""
import json

SEED_QUESTIONS = [
    # ---------------- ریاضی هفتم ----------------
    {
        "grade": "هفتم", "subject": "ریاضی هفتم", "lesson": "عددهای صحیح",
        "difficulty": "آسان", "question_type": "تستی",
        "question_text": "حاصل عبارت (-8) + 5 کدام است؟",
        "options": ["3-", "3", "13", "13-"], "correct_index": 0,
    },
    {
        "grade": "هفتم", "subject": "ریاضی هفتم", "lesson": "عددهای صحیح",
        "difficulty": "متوسط", "question_type": "تستی",
        "question_text": "حاصل عبارت (-3) × (-4) + 2 کدام است؟",
        "options": ["14", "10-", "10", "14-"], "correct_index": 0,
    },
    {
        "grade": "هفتم", "subject": "ریاضی هفتم", "lesson": "توان و جذر",
        "difficulty": "آسان", "question_type": "تستی",
        "question_text": "حاصل ۲ به توان ۴ (۲⁴) کدام است؟",
        "options": ["16", "8", "12", "6"], "correct_index": 0,
    },
    # ---------------- ریاضی دهم ----------------
    {
        "grade": "دهم", "subject": "ریاضی (۱)", "lesson": "مجموعه‌ها",
        "difficulty": "آسان", "question_type": "تستی",
        "question_text": "اگر A = {1, 2, 3} و B = {2, 3, 4} باشد، اشتراک دو مجموعه (A∩B) کدام است؟",
        "options": ["{2, 3}", "{1, 2, 3, 4}", "{1, 4}", "{}"], "correct_index": 0,
    },
    {
        "grade": "دهم", "subject": "ریاضی (۱)", "lesson": "معادله درجه دو",
        "difficulty": "متوسط", "question_type": "تستی",
        "question_text": "مجموع دو ریشه معادله x² - 5x + 6 = 0 کدام است؟",
        "options": ["5", "6", "5-", "1"], "correct_index": 0,
    },
    # ---------------- فیزیک دهم ----------------
    {
        "grade": "دهم", "subject": "فیزیک (۱)", "lesson": "اندازه‌گیری و یکاها",
        "difficulty": "آسان", "question_type": "تستی",
        "question_text": "یکای اندازه‌گیری «جرم» در نظام بین‌المللی یکاها (SI) کدام است؟",
        "options": ["کیلوگرم", "نیوتن", "گرم بر سانتی‌متر مکعب", "متر"], "correct_index": 0,
    },
    # ---------------- زیست‌شناسی دهم ----------------
    {
        "grade": "دهم", "subject": "زیست‌شناسی (۱)", "lesson": "سفری به درون سلول",
        "difficulty": "آسان", "question_type": "تستی",
        "question_text": "کدام اندامک سلولی مسئول اصلی تولید انرژی (ATP) در سلول‌های یوکاریوتی است؟",
        "options": ["میتوکندری", "ریبوزوم", "دستگاه گلژی", "لیزوزوم"], "correct_index": 0,
    },
    # ---------------- ادبیات فارسی دهم ----------------
    {
        "grade": "دهم", "subject": "فارسی (۱)", "lesson": "قلمرو زبانی (دستور)",
        "difficulty": "آسان", "question_type": "تستی",
        "question_text": "کدام گزینه یک «فعل ماضی ساده» است؟",
        "options": ["رفت", "می‌رود", "خواهد رفت", "برود"], "correct_index": 0,
    },
    # ---------------- شیمی دهم ----------------
    {
        "grade": "دهم", "subject": "شیمی (۱)", "lesson": "کیهان زادگاه الفبای هستی",
        "difficulty": "متوسط", "question_type": "تستی",
        "question_text": "عدد اتمی یک عنصر نشان‌دهنده تعداد کدام ذره در هسته اتم آن است؟",
        "options": ["پروتون", "نوترون", "الکترون", "پروتون و نوترون با هم"], "correct_index": 0,
    },
    # ---------------- ریاضی دوازدهم (سطح سخت / کنکوری) ----------------
    {
        "grade": "دوازدهم", "subject": "حسابان (۲)", "lesson": "مشتق",
        "difficulty": "سخت", "question_type": "تستی",
        "question_text": "مشتق تابع f(x) = x³ در نقطه x = 2 کدام است؟",
        "options": ["12", "8", "6", "24"], "correct_index": 0,
    },
    # ---------------- نمونه سوال تشریحی ----------------
    {
        "grade": "دهم", "subject": "زیست‌شناسی (۱)", "lesson": "سفری به درون سلول",
        "difficulty": "متوسط", "question_type": "تشریحی",
        "question_text": "نقش غشای سلولی را در کنترل ورود و خروج مواد از سلول توضیح دهید.",
        "model_answer": "غشای سلولی به دلیل ساختار دولایه فسفولیپیدی و پروتئین‌های غشایی، به‌صورت انتخابی برخی مواد را از خود عبور می‌دهد و مانع عبور برخی دیگر می‌شود؛ این ویژگی «نفوذپذیری انتخابی» نام دارد و از طریق مکانیسم‌هایی مانند انتشار ساده، انتشار تسهیل‌شده و انتقال فعال انجام می‌شود.",
    },
]


def seed_question_bank(db, models):
    """اگر بانک سوالات خالی بود، سوالات نمونه بالا را اضافه می‌کند (idempotent)."""
    existing_count = db.query(models.QuestionBankItem).count()
    if existing_count > 0:
        return

    for q in SEED_QUESTIONS:
        if q["question_type"] == "تشریحی":
            item = models.QuestionBankItem(
                grade=q["grade"], subject=q["subject"], lesson=q.get("lesson"),
                difficulty=q["difficulty"], question_type="تشریحی",
                question_text=q["question_text"], model_answer=q.get("model_answer", ""),
                source="manual",
            )
        else:
            item = models.QuestionBankItem(
                grade=q["grade"], subject=q["subject"], lesson=q.get("lesson"),
                difficulty=q["difficulty"], question_type="تستی",
                question_text=q["question_text"],
                options_json=json.dumps(q["options"], ensure_ascii=False),
                correct_index=q["correct_index"], source="manual",
            )
        db.add(item)
    db.commit()
