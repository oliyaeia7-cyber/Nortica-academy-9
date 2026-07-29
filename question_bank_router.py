"""
مدیریت بانک سوالات آزمون از پنل ادمین. سوالاتی که از این مسیر اضافه می‌شوند
source='manual' دارند و در آزمون‌های واقعی در اولویت انتخاب هستند (به‌جای
تولید سوال با هوش مصنوعی در لحظه).

علاوه بر افزودن دستی، امکان آپلود فایل PDF سوالات هم وجود دارد: متن PDF
استخراج می‌شود و هوش مصنوعی آن را به سوالات ساخت‌یافته (تستی یا تشریحی)
تبدیل می‌کند تا در بانک سوالات ذخیره شوند.
"""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import ai_client
import models
import schemas
from admin_auth import require_admin
from curriculum import ALL_GRADES, CURRICULUM
from database import get_db
from pdf_utils import extract_pdf_text

router = APIRouter(prefix="/api/question-bank", tags=["question-bank"])


def _serialize(item: models.QuestionBankItem) -> dict:
    options = []
    if item.options_json:
        try:
            options = json.loads(item.options_json)
        except Exception:
            options = []
    return {
        "id": item.id,
        "grade": item.grade,
        "subject": item.subject,
        "lesson": item.lesson,
        "difficulty": item.difficulty,
        "question_type": item.question_type,
        "question_text": item.question_text,
        "options": options,
        "correct_index": item.correct_index,
        "model_answer": item.model_answer,
        "source": item.source,
    }


@router.get("/meta", dependencies=[Depends(require_admin)])
def question_bank_meta():
    """برای پرکردن کشویی‌های پایه/رشته/درس در فرم پنل ادمین."""
    subjects_by_grade = {}
    for grade in ALL_GRADES:
        names = set()
        for field_subjects in CURRICULUM.get(grade, {}).values():
            for s in field_subjects:
                names.add(s["name"])
        subjects_by_grade[grade] = sorted(names)
    return {"grades": ALL_GRADES, "subjects_by_grade": subjects_by_grade}


@router.get("", dependencies=[Depends(require_admin)])
def list_questions(grade: str = "", subject: str = "", db: Session = Depends(get_db)):
    q = db.query(models.QuestionBankItem)
    if grade:
        q = q.filter(models.QuestionBankItem.grade == grade)
    if subject:
        q = q.filter(models.QuestionBankItem.subject == subject)
    items = q.order_by(models.QuestionBankItem.created_at.desc()).limit(300).all()
    return {"items": [_serialize(i) for i in items]}


@router.post("", dependencies=[Depends(require_admin)])
def create_question(payload: schemas.QuestionBankCreate, db: Session = Depends(get_db)):
    text = payload.question_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="متن سوال نمی‌تواند خالی باشد.")

    if payload.question_type == "تشریحی":
        if not (payload.model_answer or "").strip():
            raise HTTPException(status_code=400, detail="برای سوال تشریحی، پاسخ نمونه لازم است.")
        item = models.QuestionBankItem(
            grade=payload.grade, subject=payload.subject.strip(),
            lesson=(payload.lesson or "").strip() or None,
            difficulty=payload.difficulty, question_type="تشریحی",
            question_text=text, model_answer=payload.model_answer.strip(),
            source="manual",
        )
    else:
        options = [o.strip() for o in (payload.options or []) if o and o.strip()]
        if len(options) != 4:
            raise HTTPException(status_code=400, detail="برای سوال تستی، دقیقاً ۴ گزینه لازم است.")
        if payload.correct_index is None or not (0 <= payload.correct_index <= 3):
            raise HTTPException(status_code=400, detail="گزینه صحیح را مشخص کن.")
        item = models.QuestionBankItem(
            grade=payload.grade, subject=payload.subject.strip(),
            lesson=(payload.lesson or "").strip() or None,
            difficulty=payload.difficulty, question_type="تستی",
            question_text=text, options_json=json.dumps(options, ensure_ascii=False),
            correct_index=payload.correct_index, source="manual",
        )

    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "message": "سوال با موفقیت به بانک سوالات اضافه شد."}


@router.delete("/{item_id}", dependencies=[Depends(require_admin)])
def delete_question(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.QuestionBankItem).filter(models.QuestionBankItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="سوال پیدا نشد.")
    db.delete(item)
    db.commit()
    return {"message": "سوال حذف شد."}


MAX_IMAGE_SIZE_BYTES = 8 * 1024 * 1024  # ۸ مگابایت برای هر عکس
MAX_IMAGES_PER_UPLOAD = 6  # سقف تعداد عکس در یک PDF چندصفحه‌ای (برای جلوگیری از کندی/هزینه زیاد)

VISION_EXTRACTION_PROMPT_TEMPLATE = (
    "این تصویر شامل یک یا چند سوال امتحانی درس «{subject}» پایه {grade} است (ممکن است تستی "
    "چهارگزینه‌ای، تشریحی، یا هر دو با هم باشد؛ ممکن است دست‌نویس یا چاپی/اسکن‌شده باشد). "
    "متن تصویر را با دقت بخوان و هم «سوالات» و هم «پاسخ‌ها»یی که در تصویر نوشته شده را استخراج کن.\n\n"
    "برای هر سوال:\n"
    "- اگر سوال تستی چهارگزینه‌ای است: نوع را \"تستی\" بگذار و ۴ گزینه را دقیقاً همان‌طور که نوشته شده "
    "استخراج کن. اگر پاسخ صحیح در تصویر مشخص شده (مثلاً علامت‌گذاری‌شده یا جدا نوشته شده)، همان را به‌عنوان "
    "correct_index (بر مبنای صفر) بگذار؛ اگر مشخص نبود، بر اساس دانش خودت صحیح‌ترین گزینه را انتخاب کن.\n"
    "- اگر سوال تشریحی است: نوع را \"تشریحی\" بگذار. اگر پاسخ/راه‌حل در تصویر نوشته شده، آن را در model_answer "
    "بیاور؛ اگر پاسخی در تصویر نبود، خودت یک پاسخ کامل و صحیح بنویس.\n"
    "- اگر تصویر سوال امتحانی نیست یا چیزی برای استخراج نبود، آرایه خالی برگردان.\n\n"
    "خروجی را فقط JSON خالص (بدون توضیح یا Markdown) با این ساختار بده:\n"
    '[{{"question_type": "تستی", "question": "متن سوال", "options": ["گزینه۱","گزینه۲","گزینه۳","گزینه۴"], '
    '"correct_index": 0}}, {{"question_type": "تشریحی", "question": "متن سوال", "model_answer": "پاسخ کامل"}}]'
)


def _extract_images_from_pdf(content: bytes) -> list:
    """از یک فایل PDF (که ممکن است اسکن‌شده/تصویری باشد)، عکس‌های داخلش را
    با pypdf استخراج می‌کند (بدون نیاز به poppler/pdf2image). هر آیتم:
    (image_bytes, mime_type). هر عکس با PIL به PNG معتبر تبدیل می‌شود تا
    فرمت آن همیشه قابل‌اعتماد باشد (فارغ از نوع encoding داخل PDF)."""
    from pypdf import PdfReader
    import io as _io

    images = []
    try:
        reader = PdfReader(_io.BytesIO(content))
        for page in reader.pages:
            for img in page.images:
                try:
                    buf = _io.BytesIO()
                    pil_image = img.image
                    if pil_image.mode not in ("RGB", "L"):
                        pil_image = pil_image.convert("RGB")
                    pil_image.save(buf, format="PNG")
                    images.append((buf.getvalue(), "image/png"))
                except Exception:
                    continue
                if len(images) >= MAX_IMAGES_PER_UPLOAD:
                    return images
    except Exception:
        pass
    return images


def _save_extracted_items(items, grade, subject, lesson, difficulty, db: Session) -> tuple:
    saved_count = 0
    skipped_count = 0
    for q in items:
        question_text = (q.get("question") or "").strip()
        q_type = q.get("question_type") or "تستی"
        if not question_text:
            skipped_count += 1
            continue

        if q_type == "تشریحی":
            model_answer = (q.get("model_answer") or "").strip()
            if not model_answer:
                skipped_count += 1
                continue
            item = models.QuestionBankItem(
                grade=grade, subject=subject.strip(), lesson=(lesson or "").strip() or None,
                difficulty=difficulty, question_type="تشریحی",
                question_text=question_text, model_answer=model_answer, source="ai_extracted",
            )
        else:
            options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
            correct_index = q.get("correct_index")
            if len(options) != 4 or correct_index is None or not (0 <= int(correct_index) <= 3):
                skipped_count += 1
                continue
            item = models.QuestionBankItem(
                grade=grade, subject=subject.strip(), lesson=(lesson or "").strip() or None,
                difficulty=difficulty, question_type="تستی",
                question_text=question_text, options_json=json.dumps(options, ensure_ascii=False),
                correct_index=int(correct_index), source="ai_extracted",
            )
        db.add(item)
        saved_count += 1

    db.commit()
    return saved_count, skipped_count


@router.post("/upload-image", dependencies=[Depends(require_admin)])
async def upload_question_image(
    file: UploadFile = File(...),
    grade: str = Form(...),
    subject: str = Form(...),
    lesson: str = Form(""),
    difficulty: str = Form("متوسط"),
    db: Session = Depends(get_db),
):
    """آپلود عکس (یا PDF اسکن‌شده/شامل عکس) از برگه سوالات؛ با هوش مصنوعی
    تصویری (Gemini Vision) هم سوالات و هم پاسخ‌های نوشته‌شده در آن استخراج
    و مستقیم به بانک سوالات اضافه می‌شوند."""
    if not ai_client.has_ai_key():
        raise HTTPException(
            status_code=400,
            detail="برای استخراج سوال از عکس، باید کلید هوش مصنوعی (GEMINI_API_KEY) روی سرور تنظیم شده باشد.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="فایل خالی است.")

    is_pdf = (file.content_type == "application/pdf") or (file.filename or "").lower().endswith(".pdf")
    is_image = (file.content_type or "").startswith("image/")

    if not is_pdf and not is_image:
        raise HTTPException(status_code=400, detail="فقط فایل عکس (jpg/png) یا PDF مجاز است.")

    if is_pdf:
        images = _extract_images_from_pdf(content)
        if not images:
            raise HTTPException(
                status_code=400,
                detail="هیچ عکسی داخل این PDF پیدا نشد. اگر فایل شما متنی است (نه اسکن/عکس)، از بخش «آپلود PDF سوالات» بالا استفاده کن.",
            )
    else:
        if len(content) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="حجم عکس نباید بیشتر از ۸ مگابایت باشد.")
        mime = file.content_type or "image/jpeg"
        images = [(content, mime)]

    total_saved = 0
    total_skipped = 0
    any_success = False
    for image_bytes, mime_type in images:
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            continue
        prompt = VISION_EXTRACTION_PROMPT_TEMPLATE.format(subject=subject, grade=grade)
        parsed = ai_client.ask_ai_vision_json(image_bytes, mime_type, prompt, max_tokens=4000)
        if not parsed:
            continue
        any_success = True
        saved, skipped = _save_extracted_items(parsed, grade, subject, lesson, difficulty, db)
        total_saved += saved
        total_skipped += skipped

    if not any_success:
        raise HTTPException(
            status_code=502,
            detail="هوش مصنوعی نتوانست سوالی از این فایل استخراج کند. لطفاً کیفیت عکس را بررسی کن یا سوالات را دستی وارد کن.",
        )

    return {
        "message": f"{total_saved} سوال (همراه با پاسخ) از فایل استخراج و به بانک سوالات اضافه شد"
        + (f" ({total_skipped} مورد نامعتبر رد شد)." if total_skipped else "."),
        "saved_count": total_saved,
        "skipped_count": total_skipped,
        "images_processed": len(images),
    }


def _extract_pdf_text(content: bytes) -> str:
    full_text = extract_pdf_text(content)
    if not full_text:
        raise HTTPException(
            status_code=400,
            detail="متنی از PDF استخراج نشد. اگر فایل اسکن‌شده (تصویر) است، فعلاً این حالت پشتیبانی نمی‌شود.",
        )
    return full_text


def _ai_parse_questions_from_text(text: str, question_type: str, subject: str, grade: str):
    if not ai_client.has_ai_key():
        raise HTTPException(
            status_code=400,
            detail="برای استخراج خودکار سوال از PDF، باید کلید هوش مصنوعی (GEMINI_API_KEY) روی سرور تنظیم شده باشد.",
        )

    # برای جلوگیری از سنگین‌شدن درخواست، متن را به یک اندازه معقول محدود می‌کنیم
    trimmed = text[:14000]

    if question_type == "تشریحی":
        prompt = (
            f"متن زیر از یک فایل PDF سوالات تشریحی درس «{subject}» پایه {grade} استخراج شده است. "
            "سوالات و پاسخ‌های تشریحی موجود در متن را شناسایی کن و آن‌ها را دقیقاً به همان شکلی که در متن "
            "آمده (بدون تغییر محتوا، فقط تمیزکاری فاصله‌ها/خطاهای OCR جزئی) استخراج کن. اگر پاسخ نمونه در متن "
            "موجود نبود، یک پاسخ کامل و صحیح خودت بنویس.\n\n"
            f"متن PDF:\n{trimmed}\n\n"
            "خروجی را فقط JSON خالص (بدون توضیح یا Markdown) با این ساختار بده:\n"
            '[{"question": "متن سوال", "model_answer": "پاسخ نمونه"}]'
        )
    else:
        prompt = (
            f"متن زیر از یک فایل PDF سوالات تستی چهارگزینه‌ای درس «{subject}» پایه {grade} استخراج شده است. "
            "سوالات، گزینه‌ها و گزینه صحیح را دقیقاً همان‌طور که در متن آمده (بدون تغییر محتوا، فقط تمیزکاری "
            "فاصله‌ها/خطاهای OCR جزئی) شناسایی و استخراج کن. اگر گزینه صحیح در متن مشخص نشده بود، بر اساس "
            "دانش خودت صحیح‌ترین گزینه را انتخاب کن.\n\n"
            f"متن PDF:\n{trimmed}\n\n"
            "خروجی را فقط JSON خالص (بدون توضیح یا Markdown) با این ساختار بده:\n"
            '[{"question": "متن سوال", "options": ["گزینه۱","گزینه۲","گزینه۳","گزینه۴"], "correct_index": 0}]'
        )

    parsed = ai_client.ask_ai_json(prompt, max_tokens=4000)
    if not parsed:
        raise HTTPException(
            status_code=502,
            detail="هوش مصنوعی نتوانست سوالات را از این PDF استخراج کند. لطفاً فایل را بررسی کن یا سوالات را دستی وارد کن.",
        )
    return parsed


@router.post("/upload-pdf", dependencies=[Depends(require_admin)])
async def upload_question_pdf(
    file: UploadFile = File(...),
    grade: str = Form(...),
    subject: str = Form(...),
    lesson: str = Form(""),
    difficulty: str = Form("متوسط"),
    question_type: str = Form("تستی"),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="فقط فایل PDF مجاز است.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="فایل خالی است.")
    if len(content) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="حجم فایل نباید بیشتر از ۱۲ مگابایت باشد.")

    pdf_text = _extract_pdf_text(content)
    parsed_questions = _ai_parse_questions_from_text(pdf_text, question_type, subject, grade)

    saved_count = 0
    skipped_count = 0
    for q in parsed_questions:
        question_text = (q.get("question") or "").strip()
        if not question_text:
            skipped_count += 1
            continue

        if question_type == "تشریحی":
            model_answer = (q.get("model_answer") or "").strip()
            if not model_answer:
                skipped_count += 1
                continue
            item = models.QuestionBankItem(
                grade=grade, subject=subject.strip(), lesson=(lesson or "").strip() or None,
                difficulty=difficulty, question_type="تشریحی",
                question_text=question_text, model_answer=model_answer, source="manual",
            )
        else:
            options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
            correct_index = q.get("correct_index")
            if len(options) != 4 or correct_index is None or not (0 <= correct_index <= 3):
                skipped_count += 1
                continue
            item = models.QuestionBankItem(
                grade=grade, subject=subject.strip(), lesson=(lesson or "").strip() or None,
                difficulty=difficulty, question_type="تستی",
                question_text=question_text, options_json=json.dumps(options, ensure_ascii=False),
                correct_index=correct_index, source="manual",
            )
        db.add(item)
        saved_count += 1

    db.commit()

    return {
        "message": f"{saved_count} سوال از PDF استخراج و ذخیره شد" + (f" ({skipped_count} مورد نامعتبر رد شد)." if skipped_count else "."),
        "saved_count": saved_count,
        "skipped_count": skipped_count,
    }
