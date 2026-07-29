"""
موتور آزمون نورتیکا — نسخه مبتنی بر «بانک سوالات» به‌جای تولید سوال با
هوش مصنوعی در لحظه.

اولویت با سوالاتی است که از پنل ادمین به بانک سوالات اضافه شده‌اند
(QuestionBankItem با source='manual'). اگر برای یک ترکیب پایه/درس/فصل/سطح،
تعداد سوال دستی کافی نباشد، از یک موتور تولید خودکار (auto) که مستقیماً از
سرفصل واقعی کتاب‌های درسی (curriculum.py) استفاده می‌کند، به‌عنوان مکمل
استفاده می‌شود. این یعنی هیچ فصلی از قلم نمی‌افتد (پوشش کامل)، ولی هر چه
سوالات دستی بیشتری از پنل ادمین اضافه شود، کیفیت و تنوع آزمون‌ها بیشتر
می‌شود.

نکته مهم: تحلیل پاسخ‌های غلط (analyze_wrong_answers) و ارزیابی پاسخ‌های
تشریحی (analyze_essay_answers) همچنان از هوش مصنوعی استفاده می‌کنند — طبق
درخواست، فقط «تولید سوال» با AI حذف شده، نه تحلیل نتیجه.
"""
import json
import random

from curriculum import get_subjects, ALL_GRADES
import ai_client
import models

FIELD_KEYS = ["عمومی", "ریاضی فیزیک", "علوم تجربی", "علوم انسانی", "فنی حرفه‌ای"]

# -----------------------------------------------------------------------
# موتور تولید خودکار (مکمل) — بر اساس سرفصل واقعی کتاب درسی، با تنوع بالا
# تا مشکل «تکراری بودن سوالات» رفع شود (هم برای متن سوال، هم گزینه‌ها)
# -----------------------------------------------------------------------
QUESTION_TEMPLATES = {
    "آسان": [
        "کدام گزینه، تعریف درست «{topic}» در درس {subject} است؟",
        "مفهوم «{topic}» در درس {subject} به کدام مورد اشاره دارد؟",
        "کدام مورد جزو نکات پایه‌ای «{topic}» ({subject}) محسوب می‌شود؟",
        "در بخش «{topic}» از درس {subject}، کدام گزینه صحیح است؟",
    ],
    "متوسط": [
        "کدام گزینه در ارتباط با «{topic}» در درس {subject} صحیح است؟",
        "در بررسی «{topic}» ({subject})، کدام گزینه نادرست است؟",
        "کاربرد صحیح «{topic}» در حل مسئله‌های درس {subject} کدام است؟",
        "کدام یک از موارد زیر، ارتباط درستی با «{topic}» در {subject} دارد؟",
        "دانش‌آموزی که «{topic}» را درست فهمیده باشد، کدام گزینه را انتخاب می‌کند؟",
    ],
    "سخت": [
        "در یک مسئله ترکیبی از «{topic}» در درس {subject}، کدام گزینه با تحلیل دقیق صحیح است؟ (سطح کنکوری)",
        "کدام یک از موارد زیر، نکته کلیدی و کمتردیده‌شده «{topic}» در {subject} است؟",
        "در تحلیل چندمرحله‌ای «{topic}» ({subject})، کدام گزینه در همه حالات صادق است؟",
        "کدام گزینه، رایج‌ترین اشتباه دانش‌آموزان درباره «{topic}» در {subject} را نشان می‌دهد؟",
    ],
}

CORRECT_PATTERNS = [
    "بیانی دقیق و منطبق با تعریف اصلی «{topic}»",
    "کاربرد صحیح مفهوم «{topic}» در حل مسئله درس {subject}",
    "ارتباط درست «{topic}» با سایر مباحث درس {subject}",
    "نتیجه‌گیری منطقی و صحیح بر اساس «{topic}»",
    "توضیحی که با کتاب درسی درباره «{topic}» کاملاً هم‌خوانی دارد",
]

DISTRACTOR_PATTERNS = [
    "بیانی نادرست و متناقض با تعریف «{topic}»",
    "مفهومی نامرتبط با «{topic}» در {subject}",
    "برداشت اشتباه رایج درباره «{topic}»",
    "تعریفی مربوط به مبحث دیگری از درس {subject}",
    "نتیجه‌گیری عجولانه و بدون استدلال کافی درباره «{topic}»",
    "ترکیب نادرست «{topic}» با مفهومی از فصل دیگر",
]


def _fallback_topics(subject_name):
    return ["مفاهیم پایه", "نکات تستی مهم", "کاربردهای درس", "جمع‌بندی فصل"]


def _resolve_topics(subject, lesson, grade):
    topics = None
    search_order = ([grade] + ALL_GRADES) if grade else ALL_GRADES
    for g in search_order:
        all_subjects = []
        for fk in FIELD_KEYS:
            all_subjects += get_subjects(g, fk)
        for field_subjects in all_subjects:
            if field_subjects["name"] == subject or subject in field_subjects["name"]:
                topics = field_subjects.get("topics")
                break
        if topics:
            break
    if not topics:
        topics = _fallback_topics(subject)

    if lesson and lesson.strip():
        matched = [t for t in topics if lesson.strip() in t or t in lesson.strip()]
        if matched:
            return matched
    return topics


def _shuffle_options(options, correct_index):
    """گزینه‌ها را به‌هم می‌ریزد و اندیس گزینه صحیح جدید را برمی‌گرداند
    (برای این‌که حتی یک سوال ثابت هم هر بار با ترتیب گزینه متفاوت نمایش
    داده شود و جای گزینه صحیح قابل حفظ‌کردن نباشد)."""
    indexed = list(enumerate(options))
    random.shuffle(indexed)
    new_options = [text for _, text in indexed]
    new_correct = next(pos for pos, (orig_idx, _) in enumerate(indexed) if orig_idx == correct_index)
    return new_options, new_correct


def _auto_generate_mcq(subject, grade, topics, count, difficulty, avoid_topics=None):
    templates = QUESTION_TEMPLATES.get(difficulty, QUESTION_TEMPLATES["متوسط"])
    avoid_topics = avoid_topics or set()
    # موضوعات استفاده‌نشده در سوالات دستی را در اولویت قرار بده تا تنوع بیشتر شود
    ordered_topics = [t for t in topics if t not in avoid_topics] + [t for t in topics if t in avoid_topics]
    if not ordered_topics:
        ordered_topics = topics

    questions = []
    used_combinations = set()
    attempts = 0
    while len(questions) < count and attempts < count * 8:
        attempts += 1
        topic = ordered_topics[attempts % len(ordered_topics)]
        template = random.choice(templates)
        combo_key = (topic, template)
        if combo_key in used_combinations and len(ordered_topics) * len(templates) > count:
            continue
        used_combinations.add(combo_key)

        question_text = template.format(topic=topic, subject=subject)
        correct_text = random.choice(CORRECT_PATTERNS).format(topic=topic, subject=subject)
        distractors = random.sample(DISTRACTOR_PATTERNS, 3)
        options_texts = [correct_text] + [d.format(topic=topic, subject=subject) for d in distractors]
        shuffled_options, correct_index = _shuffle_options(options_texts, 0)

        questions.append({
            "question": question_text,
            "options": shuffled_options,
            "correct_index": correct_index,
            "topic": topic,
            "source": "auto",
        })
    return questions


def _auto_generate_essay(subject, topics, count, difficulty):
    questions = []
    for i in range(count):
        topic = topics[i % len(topics)]
        questions.append({
            "question": f"«{topic}» را در درس {subject} با ذکر جزئیات و مثال توضیح دهید. (سطح {difficulty})",
            "model_answer": f"پاسخ کامل باید تعریف «{topic}»، ارتباط آن با مباحث درس {subject} و حداقل یک مثال کاربردی را شامل شود.",
            "topic": topic,
            "source": "auto",
        })
    return questions


# -----------------------------------------------------------------------
# استخراج سوالات دستی (اضافه‌شده از پنل ادمین) از دیتابیس
# -----------------------------------------------------------------------
def _fetch_manual_questions(db, subject, lesson, grade, difficulty, question_type, limit):
    if db is None:
        return []
    q = db.query(models.QuestionBankItem).filter(
        models.QuestionBankItem.subject == subject,
        models.QuestionBankItem.difficulty == difficulty,
        models.QuestionBankItem.question_type == question_type,
        models.QuestionBankItem.source.in_(["manual", "ai_extracted"]),
    )
    if grade:
        q = q.filter(models.QuestionBankItem.grade == grade)

    items = q.all()

    # اگر فصل مشخص شده و سوال مرتبط با همان فصل موجود بود، اول آن‌ها را بردار
    if lesson and lesson.strip():
        matched = [it for it in items if it.lesson and lesson.strip() in it.lesson]
        rest = [it for it in items if it not in matched]
        items = matched + rest

    random.shuffle(items)
    return items[:limit]


def generate_quiz(db, subject, lesson, grade, question_count=10, difficulty="متوسط", question_type="تستی"):
    question_count = max(1, min(question_count, 30))
    if difficulty not in ("آسان", "متوسط", "سخت"):
        difficulty = "متوسط"

    manual_items = _fetch_manual_questions(db, subject, lesson, grade, difficulty, question_type, question_count)
    manual_topics_used = {it.lesson for it in manual_items if it.lesson}

    questions = []
    if question_type == "تشریحی":
        for it in manual_items:
            questions.append({
                "question": it.question_text,
                "model_answer": it.model_answer or "",
                "topic": it.lesson or subject,
                "source": "manual",
            })
        remaining = question_count - len(questions)
        if remaining > 0:
            topics = _resolve_topics(subject, lesson, grade)
            questions += _auto_generate_essay(subject, topics, remaining, difficulty)
    else:
        for it in manual_items:
            options = json.loads(it.options_json) if it.options_json else []
            if len(options) != 4 or it.correct_index is None:
                continue
            shuffled_options, correct_index = _shuffle_options(options, it.correct_index)
            questions.append({
                "question": it.question_text,
                "options": shuffled_options,
                "correct_index": correct_index,
                "topic": it.lesson or subject,
                "source": "manual",
            })
        remaining = question_count - len(questions)
        if remaining > 0:
            topics = _resolve_topics(subject, lesson, grade)
            questions += _auto_generate_mcq(subject, grade, topics, remaining, difficulty, avoid_topics=manual_topics_used)

    random.shuffle(questions)
    questions = questions[:question_count]
    for i, q in enumerate(questions):
        q["id"] = i + 1

    manual_count = sum(1 for q in questions if q.get("source") == "manual")
    quality_note = None
    if manual_count == 0:
        quality_note = (
            "این آزمون فعلاً از موتور تولید خودکار بر اساس سرفصل کتاب درسی ساخته شده؛ "
            "با افزودن سوال دستی از پنل ادمین برای این درس، کیفیت آزمون‌های بعدی بهتر می‌شود."
        )

    return {
        "subject": subject,
        "lesson": lesson or subject,
        "grade": grade,
        "question_count": len(questions),
        "difficulty": difficulty,
        "question_type": question_type,
        "engine": "question_bank",
        "quality_note": quality_note,
        "questions": questions,
    }


# -----------------------------------------------------------------------
# تحلیل پاسخ‌های غلط و ارزیابی پاسخ‌های تشریحی — همچنان با هوش مصنوعی
# (طبق درخواست: فقط تولید سوال از AI حذف شد، نه تحلیل نتیجه)
# -----------------------------------------------------------------------
def analyze_wrong_answers(subject, grade, wrong_items):
    """
    wrong_items: لیستی از دیکشنری {question, options, correct_index, user_index}
    خروجی: تحلیل هوش مصنوعی برای هر سوال غلط، یا تحلیل ساده در صورت نبود کلید API
    """
    if not wrong_items:
        return []

    if not ai_client.has_ai_key():
        result = []
        for item in wrong_items:
            correct_text = item["options"][item["correct_index"]] if item.get("options") else ""
            result.append({
                "question": item["question"],
                "your_answer": item["options"][item["user_index"]] if item.get("options") and 0 <= item.get("user_index", -1) < len(item["options"]) else "بدون پاسخ",
                "correct_answer": correct_text,
                "explanation": f"پاسخ صحیح «{correct_text}» است. لطفاً مبحث مربوط به این سوال را در درس {subject} مجدداً مرور کنید.",
            })
        return result

    items_text = json.dumps(wrong_items, ensure_ascii=False)
    prompt = (
        f"شما دستیار آموزشی نورتیکا هستید. دانش‌آموز پایه {grade} در درس «{subject}» به سوالات زیر پاسخ غلط داده است "
        f"(هر آیتم شامل question، options، correct_index و user_index است):\n{items_text}\n\n"
        "برای هر سوال، توضیح بده چرا پاسخ دانش‌آموز غلط بوده و پاسخ صحیح چیست، به زبانی ساده و دلگرم‌کننده که دانش‌آموز اشتباهش را بفهمد و اصلاح کند. "
        "خروجی را فقط JSON خالص با این ساختار بده:\n"
        '[{"question": "...", "your_answer": "...", "correct_answer": "...", "explanation": "..."}]'
    )
    parsed = ai_client.ask_ai_json(prompt, max_tokens=2000)
    if parsed:
        return parsed

    result = []
    for item in wrong_items:
        correct_text = item["options"][item["correct_index"]] if item.get("options") else ""
        result.append({
            "question": item["question"],
            "your_answer": item["options"][item["user_index"]] if item.get("options") and 0 <= item.get("user_index", -1) < len(item["options"]) else "بدون پاسخ",
            "correct_answer": correct_text,
            "explanation": f"پاسخ صحیح «{correct_text}» است. لطفاً مبحث مربوط به این سوال را در درس {subject} مجدداً مرور کنید.",
        })
    return result


def analyze_essay_answers(subject, grade, answers):
    """
    answers: لیست {question, student_answer, model_answer}
    خروجی: تحلیل/نمره هر پاسخ تشریحی
    """
    if not ai_client.has_ai_key():
        result = []
        for a in answers:
            result.append({
                "question": a["question"],
                "student_answer": a["student_answer"],
                "correct_answer": a.get("model_answer", ""),
                "score_percent": 50,
                "explanation": "برای تحلیل دقیق پاسخ تشریحی، کلید هوش مصنوعی باید فعال باشد. این یک ارزیابی پیش‌فرض است.",
            })
        return result

    items_text = json.dumps(answers, ensure_ascii=False)
    prompt = (
        f"شما معلم درس «{subject}» پایه {grade} هستید. پاسخ‌های تشریحی زیر را ارزیابی کن "
        f"(هر آیتم شامل question، student_answer و model_answer است):\n{items_text}\n\n"
        "برای هر پاسخ، درصد صحت (0 تا 100)، پاسخ صحیح کامل و توضیح دلگرم‌کننده برای اصلاح اشتباه دانش‌آموز بده. "
        "خروجی را فقط JSON خالص با این ساختار بده:\n"
        '[{"question": "...", "student_answer": "...", "correct_answer": "...", "score_percent": 80, "explanation": "..."}]'
    )
    parsed = ai_client.ask_ai_json(prompt, max_tokens=2500)
    if parsed:
        return parsed

    result = []
    for a in answers:
        result.append({
            "question": a["question"],
            "student_answer": a["student_answer"],
            "correct_answer": a.get("model_answer", ""),
            "score_percent": 50,
            "explanation": "در حال حاضر امکان تحلیل هوشمند این پاسخ وجود نداشت.",
        })
    return result
