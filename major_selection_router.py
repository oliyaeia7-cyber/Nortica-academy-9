"""
انتخاب رشته هوشمند نورتیکا.

موتور پیشنهاد ابتدا از بانک کدرشته‌های واقعی (UniversityMajorCode — که از پنل
ادمین به‌صورت تکی یا با آپلود CSV دفترچه سازمان سنجش پر می‌شود) استفاده
می‌کند. اگر برای ترکیب رتبه/رشته/شهر داده کافی در دیتابیس نبود، به‌عنوان
مکمل از هوش مصنوعی کمک گرفته می‌شود — با ذکر صریح این‌که پیشنهاد هوش مصنوعی
تخمینی است و جایگزین دفترچه رسمی سازمان سنجش نیست.

ورودی دانش‌آموز می‌تواند شامل متن آزاد و/یا یک فایل PDF (مثلاً کارنامه یا
ریز نمرات) هم باشد که متن آن استخراج و به‌عنوان زمینه اضافه به هوش مصنوعی
داده می‌شود.
"""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

import ai_client
import models
import schemas
from admin_auth import require_admin
from database import get_db
from pdf_export import build_major_selection_pdf
from pdf_utils import extract_pdf_text

router = APIRouter(tags=["major-selection"])

MAX_CANDIDATES = 150
RANK_MARGIN_RATIO = 0.35  # حاشیه اطمینان روی بازه رتبه قبولی سال قبل

CHUNK_CHAR_SIZE = 12000  # هر تکه متن که یک‌بار به هوش مصنوعی داده می‌شود


def _ai_parse_major_codes_chunk(text_chunk: str):
    """یک تکه از متن PDF را به هوش مصنوعی می‌دهد تا کدرشته‌های داخلش را
    به‌صورت ساخت‌یافته (JSON) استخراج کند. اگر کلید هوش مصنوعی نبود یا خطا
    داد، لیست خالی برمی‌گرداند."""
    if not ai_client.has_ai_key() or not text_chunk.strip():
        return []
    prompt = (
        "متن زیر بخشی از یک فایل PDF دفترچه/فهرست کدرشته‌های دانشگاهی ایران است. "
        "تمام ردیف‌های کدرشته موجود در این متن را دقیقاً همان‌طور که آمده (بدون تغییر یا حدس بی‌جا) استخراج کن. "
        "برای هر ردیف: کد رشته، نام دانشگاه، نام رشته، شهر، نوع دانشگاه (دولتی/آزاد/غیرانتفاعی/پیام نور/شبانه) "
        "و در صورت وجود، بازه رتبه قبولی (حداقل و حداکثر). اگر اطلاعاتی برای یک فیلد در متن نبود، آن را خالی بگذار "
        "(حدس نزن).\n\n"
        f"متن:\n{text_chunk}\n\n"
        "خروجی را فقط JSON خالص (بدون توضیح یا Markdown) با این ساختار بده:\n"
        '[{"code": "...", "university_name": "...", "major_name": "...", "city": "...", '
        '"ownership_type": "...", "min_rank": 12000, "max_rank": 15000}]\n'
        "اگر هیچ ردیف کدرشته معتبری در متن پیدا نکردی، آرایه خالی [] برگردان."
    )
    parsed = ai_client.ask_ai_json(prompt, max_tokens=4000)
    return parsed if isinstance(parsed, list) else []


def _parse_pdf_to_major_codes(content: bytes, max_pages: int, max_chunks: int):
    """متن PDF را استخراج و تکه‌تکه به هوش مصنوعی می‌دهد تا کدرشته‌ها را
    شناسایی کند. برای فایل‌های خیلی بزرگ (مثل دفترچه کامل سنجش با هزاران
    ردیف)، فقط بخشی که در max_pages/max_chunks جا می‌شود پردازش می‌شود —
    برای دیتاست کامل، بهتر است فایل به چند بخش کوچک‌تر تقسیم و چندبار
    آپلود شود، یا (برای داده‌های جدولی) از آپلود CSV استفاده شود."""
    full_text = extract_pdf_text(content, max_pages=max_pages)
    if not full_text:
        return []

    chunks = [full_text[i:i + CHUNK_CHAR_SIZE] for i in range(0, len(full_text), CHUNK_CHAR_SIZE)][:max_chunks]
    all_codes = []
    for chunk in chunks:
        all_codes.extend(_ai_parse_major_codes_chunk(chunk))
    return all_codes


# ---------------------------------------------------------------------
# موتور پیشنهاد برای دانش‌آموز
# ---------------------------------------------------------------------
@router.post("/api/major-selection/recommend")
async def recommend_majors(
    full_name: str = Form(...),
    grade: str = Form(...),
    diploma_rank: str = Form(...),
    konkur_rank: str = Form(...),
    target_field: str = Form(...),
    target_city: str = Form(...),
    extra_text: str = Form(""),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    try:
        diploma_score_val = float(diploma_rank) if diploma_rank and diploma_rank.strip() else None
    except ValueError:
        diploma_score_val = None
    konkur_rank_int = int(konkur_rank) if konkur_rank and konkur_rank.strip().isdigit() else None

    if diploma_score_val is None or konkur_rank_int is None or not target_city.strip():
        raise HTTPException(status_code=400, detail="نمره دیپلم، رتبه کنکور و شهر مورد نظر الزامی است.")

    pdf_context = ""
    pdf_codes_raw = []
    if file is not None:
        content = await file.read()
        if content:
            try:
                pdf_context = extract_pdf_text(content, max_pages=60)[:8000]
            except HTTPException:
                pdf_context = ""
            # علاوه بر متن زمینه، تلاش می‌کنیم کدرشته‌های داخل خودِ فایل را هم
            # به‌صورت ساخت‌یافته استخراج کنیم تا جست‌وجو دقیقاً «بین همین‌ها» انجام شود
            try:
                pdf_codes_raw = _parse_pdf_to_major_codes(content, max_pages=60, max_chunks=4)
            except HTTPException:
                pdf_codes_raw = []

    def _in_rank_window(min_rank, max_rank):
        if not konkur_rank_int:
            return True
        if min_rank is None and max_rank is None:
            return True
        margin = max(500, int(konkur_rank_int * RANK_MARGIN_RATIO))
        lo, hi = konkur_rank_int - margin, konkur_rank_int + margin
        return (min_rank or 0) <= hi and (max_rank or 10**9) >= lo

    # ---------------- ۱) کدرشته‌های استخراج‌شده از فایل PDF کاربر (اولویت اول) ----------------
    pdf_candidates = []
    target_field_norm = target_field.strip()
    for c in pdf_codes_raw:
        major_name = (c.get("major_name") or "").strip()
        if not major_name or not c.get("university_name"):
            continue
        if target_field_norm and target_field_norm not in major_name and major_name not in target_field_norm:
            continue
        if not _in_rank_window(c.get("min_rank"), c.get("max_rank")):
            continue
        pdf_candidates.append({
            "code": c.get("code"), "university_name": c.get("university_name"),
            "major_name": major_name, "city": c.get("city"),
            "ownership_type": c.get("ownership_type"),
            "min_rank": c.get("min_rank"), "max_rank": c.get("max_rank"),
        })

    # ---------------- ۲) جست‌وجو در بانک کدرشته واقعی ذخیره‌شده در سایت ----------------
    query = db.query(models.UniversityMajorCode).filter(
        models.UniversityMajorCode.major_name.ilike(f"%{target_field_norm}%")
    )
    city_filtered = []
    if target_city and target_city.strip():
        city_filtered = query.filter(models.UniversityMajorCode.city.ilike(f"%{target_city.strip()}%")).all()

    all_matching = city_filtered if len(city_filtered) >= 15 else query.all()

    db_candidates = []
    for c in all_matching:
        if _in_rank_window(c.min_rank, c.max_rank):
            db_candidates.append({
                "code": c.code, "university_name": c.university_name, "major_name": c.major_name,
                "city": c.city, "ownership_type": c.ownership_type,
                "min_rank": c.min_rank, "max_rank": c.max_rank,
            })

    # ترکیب: اول نتایج داخل فایل کاربر (چون صریحاً خواسته «بین این‌ها» جست‌وجو شود)، بعد بانک سایت — با حذف موارد تکراری
    seen = set()
    candidates_dicts = []
    for c in pdf_candidates + db_candidates:
        key = (c.get("university_name"), c.get("major_name"), c.get("code"))
        if key in seen:
            continue
        seen.add(key)
        candidates_dicts.append(c)
        if len(candidates_dicts) >= MAX_CANDIDATES:
            break

    used_pdf_search = bool(pdf_candidates)

    # ---------------- تحلیل و توصیه (متنی) ----------------
    student_context = (
        f"نام: {full_name}\nپایه: {grade}\nنمره دیپلم: {diploma_score_val if diploma_score_val is not None else 'نامشخص'}\n"
        f"رتبه کنکور: {konkur_rank_int or 'نامشخص'}\nرشته مورد نظر: {target_field}\n"
        f"شهر مورد نظر: {target_city or 'بدون محدودیت خاص'}"
    )
    if extra_text.strip():
        student_context += f"\nتوضیحات اضافه دانش‌آموز: {extra_text.strip()}"
    if pdf_context:
        student_context += f"\nمتن استخراج‌شده از فایل ضمیمه:\n{pdf_context}"

    result_text = None
    if ai_client.has_ai_key():
        if candidates_dicts:
            codes_summary = "\n".join(
                f"- {c['university_name']} / {c['major_name']} / شهر {c.get('city') or '-'} / "
                f"نوع {c.get('ownership_type') or '-'} / کد {c.get('code') or '-'} / "
                f"بازه رتبه سال قبل {c.get('min_rank') or '-'}-{c.get('max_rank') or '-'}"
                for c in candidates_dicts[:60]
            )
            prompt = (
                "تو «انتخاب رشته هوشمند نورتیکا» هستی، یک مشاور انتخاب رشته باتجربه و دلسوز.\n"
                f"اطلاعات دانش‌آموز:\n{student_context}\n\n"
                f"این فهرست، نتایج واقعی موجود در بانک اطلاعاتی نورتیکا است (به کد و رتبه‌ها دست نزن، "
                f"دقیقاً همین‌ها را مبنا قرار بده):\n{codes_summary}\n\n"
                + ("این فهرست از داخل فایل PDF‌ای که خودِ دانش‌آموز آپلود کرده استخراج شده است.\n\n" if used_pdf_search else "")
                + "یک تحلیل کوتاه و شخصی‌سازی‌شده (حداکثر ۸-۱۰ خط) بنویس: چند گزینه برتر از فهرست بالا را "
                "با دلیل معرفی کن، و یک توصیه کلی درباره استراتژی انتخاب رشته (ترکیب گزینه‌های مطمئن و "
                "بلندپروازانه) بده. لحن گرم و دلگرم‌کننده داشته باش. فقط متن ساده بده، بدون Markdown."
            )
        else:
            prompt = (
                "تو «انتخاب رشته هوشمند نورتیکا» هستی، یک مشاور انتخاب رشته باتجربه.\n"
                f"اطلاعات دانش‌آموز:\n{student_context}\n\n"
                "در بانک اطلاعاتی نورتیکا برای این ترکیب رشته/شهر/رتبه، داده کافی ثبت نشده است. بر اساس "
                "دانش عمومی خودت از دانشگاه‌های ایران (دولتی، آزاد، غیرانتفاعی، پیام‌نور)، حدود ۱۰ تا ۱۵ "
                "گزینه واقع‌بینانه (نام دانشگاه و رشته) متناسب با رتبه و رشته موردنظر دانش‌آموز پیشنهاد بده. "
                "در انتهای پاسخ حتماً تأکید کن که این پیشنهادها تخمینی است و باید با دفترچه رسمی سازمان سنجش "
                "مقایسه شود. فقط متن ساده بده، بدون Markdown."
            )
        result_text = ai_client.ask_ai(prompt, max_tokens=1500)

    if not result_text:
        if candidates_dicts:
            lines = [f"بر اساس بانک اطلاعاتی نورتیکا، {len(candidates_dicts)} گزینه متناسب با رتبه و رشته مورد نظرت پیدا شد:"]
            for c in candidates_dicts[:20]:
                lines.append(f"• {c['university_name']} — {c['major_name']} ({c.get('city') or '-'}, {c.get('ownership_type') or '-'})")
            lines.append("برای بررسی کامل، جدول کامل را در فایل PDF یا فهرست زیر ببین.")
            result_text = "\n".join(lines)
        else:
            result_text = (
                "در حال حاضر برای این ترکیب رشته/شهر/رتبه، داده کافی در بانک اطلاعاتی نورتیکا ثبت نشده و "
                "امکان اتصال به هوش مصنوعی هم برقرار نیست. لطفاً بعداً دوباره امتحان کن یا با دفترچه رسمی "
                "سازمان سنجش مقایسه کن."
            )

    record = models.MajorSelectionRequest(
        full_name=full_name, grade=grade, diploma_rank=diploma_score_val, konkur_rank=konkur_rank_int,
        target_field=target_field, target_city=target_city, extra_text=extra_text,
        result_text=result_text,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "request_id": record.id,
        "result_text": result_text,
        "candidates": candidates_dicts,
        "used_database": bool(candidates_dicts),
        "used_pdf_search": used_pdf_search,
    }


@router.get("/api/major-selection/pdf/{request_id}")
def download_major_selection_pdf(request_id: int, db: Session = Depends(get_db)):
    record = db.query(models.MajorSelectionRequest).filter(models.MajorSelectionRequest.id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="درخواست پیدا نشد.")

    query = db.query(models.UniversityMajorCode).filter(
        models.UniversityMajorCode.major_name.ilike(f"%{(record.target_field or '').strip()}%")
    )
    if record.target_city and record.target_city.strip():
        city_filtered = query.filter(models.UniversityMajorCode.city.ilike(f"%{record.target_city.strip()}%")).all()
        candidates = city_filtered if len(city_filtered) >= 15 else query.limit(MAX_CANDIDATES).all()
    else:
        candidates = query.limit(MAX_CANDIDATES).all()
    candidates_dicts = [
        {
            "code": c.code, "university_name": c.university_name, "major_name": c.major_name,
            "city": c.city, "ownership_type": c.ownership_type,
            "min_rank": c.min_rank, "max_rank": c.max_rank,
        }
        for c in candidates
    ]

    pdf_bytes = build_major_selection_pdf(
        {
            "full_name": record.full_name, "grade": record.grade,
            "diploma_rank": record.diploma_rank, "konkur_rank": record.konkur_rank,
            "target_field": record.target_field, "target_city": record.target_city,
        },
        candidates_dicts,
        record.result_text or "",
    )
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=noortika-major-selection.pdf"},
    )


# ---------------------------------------------------------------------
# مدیریت بانک کدرشته از پنل ادمین
# ---------------------------------------------------------------------
@router.get("/api/major-codes", dependencies=[Depends(require_admin)])
def list_major_codes(search: str = "", db: Session = Depends(get_db)):
    q = db.query(models.UniversityMajorCode)
    if search.strip():
        like = f"%{search.strip()}%"
        q = q.filter(or_(
            models.UniversityMajorCode.major_name.ilike(like),
            models.UniversityMajorCode.university_name.ilike(like),
            models.UniversityMajorCode.city.ilike(like),
            models.UniversityMajorCode.code.ilike(like),
        ))
    items = q.order_by(models.UniversityMajorCode.created_at.desc()).limit(300).all()
    return {
        "items": [
            {
                "id": c.id, "code": c.code, "university_name": c.university_name,
                "major_name": c.major_name, "city": c.city, "ownership_type": c.ownership_type,
                "field_group": c.field_group, "min_rank": c.min_rank, "max_rank": c.max_rank,
                "notes": c.notes,
            }
            for c in items
        ],
        "total_count": db.query(models.UniversityMajorCode).count(),
    }


@router.post("/api/major-codes", dependencies=[Depends(require_admin)])
def create_major_code(payload: schemas.MajorCodeCreate, db: Session = Depends(get_db)):
    if not payload.university_name.strip() or not payload.major_name.strip():
        raise HTTPException(status_code=400, detail="نام دانشگاه و نام رشته الزامی است.")
    item = models.UniversityMajorCode(
        code=(payload.code or "").strip() or None,
        university_name=payload.university_name.strip(),
        major_name=payload.major_name.strip(),
        city=(payload.city or "").strip() or None,
        ownership_type=(payload.ownership_type or "").strip() or None,
        field_group=(payload.field_group or "").strip() or None,
        min_rank=payload.min_rank, max_rank=payload.max_rank,
        notes=(payload.notes or "").strip() or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "message": "کدرشته اضافه شد."}


@router.delete("/api/major-codes/{item_id}", dependencies=[Depends(require_admin)])
def delete_major_code(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.UniversityMajorCode).filter(models.UniversityMajorCode.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="کدرشته پیدا نشد.")
    db.delete(item)
    db.commit()
    return {"message": "کدرشته حذف شد."}


@router.post("/api/major-codes/upload-csv", dependencies=[Depends(require_admin)])
async def upload_major_codes_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    فرمت CSV مورد انتظار (ردیف اول = هدر، ترتیب ستون‌ها مهم است):
    کد,دانشگاه,رشته,شهر,نوع,گروه,حداقل_رتبه,حداکثر_رتبه,توضیحات
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="فقط فایل CSV پشتیبانی می‌شود.")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("utf-8", errors="ignore")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="فایل خالی است.")

    saved, skipped = 0, 0
    for row in rows[1:]:  # ردیف اول هدر است
        row = [c.strip() for c in row] + [""] * 9
        code, university, major, city, ownership, field_group, min_rank, max_rank, notes = row[:9]
        if not university or not major:
            skipped += 1
            continue
        item = models.UniversityMajorCode(
            code=code or None, university_name=university, major_name=major,
            city=city or None, ownership_type=ownership or None, field_group=field_group or None,
            min_rank=int(min_rank) if min_rank.isdigit() else None,
            max_rank=int(max_rank) if max_rank.isdigit() else None,
            notes=notes or None,
        )
        db.add(item)
        saved += 1
    db.commit()

    return {"message": f"{saved} کدرشته اضافه شد ({skipped} ردیف نامعتبر رد شد).", "saved_count": saved, "skipped_count": skipped}


MAX_ADMIN_PDF_SIZE_BYTES = 20 * 1024 * 1024  # ۲۰ مگابایت


@router.post("/api/major-codes/upload-pdf", dependencies=[Depends(require_admin)])
async def upload_major_codes_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    آپلود فایل PDF دفترچه/فهرست کدرشته از پنل ادمین — هوش مصنوعی محتوای فایل
    را می‌خواند و کدرشته‌ها را استخراج و در بانک اطلاعاتی ذخیره می‌کند.

    نکته مهم درباره فایل‌های خیلی بزرگ: پردازش با هوش مصنوعی محدودیت حجمی
    دارد؛ در هر آپلود حداکثر حدود ۸۰ صفحه اول فایل پردازش می‌شود. برای
    دفترچه‌های خیلی بزرگ (چند هزار ردیف)، یا فایل را به چند بخش کوچک‌تر
    تقسیم و چندبار آپلود کن، یا (برای دقت و سرعت بیشتر) از آپلود CSV
    استفاده کن.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="فقط فایل PDF مجاز است.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="فایل خالی است.")
    if len(content) > MAX_ADMIN_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="حجم فایل نباید بیشتر از ۲۰ مگابایت باشد.")

    if not ai_client.has_ai_key():
        raise HTTPException(
            status_code=400,
            detail="برای استخراج خودکار کدرشته از PDF، باید کلید هوش مصنوعی (GEMINI_API_KEY) روی سرور تنظیم شده باشد.",
        )

    parsed_codes = _parse_pdf_to_major_codes(content, max_pages=80, max_chunks=7)
    if not parsed_codes:
        raise HTTPException(
            status_code=400,
            detail="هیچ کدرشته‌ای از این PDF استخراج نشد. یا فایل اسکن‌شده (تصویر) است، یا ساختار متن قابل تشخیص نبود. آپلود CSV گزینه مطمئن‌تری است.",
        )

    saved, skipped = 0, 0
    for c in parsed_codes:
        university = (c.get("university_name") or "").strip()
        major = (c.get("major_name") or "").strip()
        if not university or not major:
            skipped += 1
            continue
        item = models.UniversityMajorCode(
            code=(c.get("code") or "").strip() or None,
            university_name=university, major_name=major,
            city=(c.get("city") or "").strip() or None,
            ownership_type=(c.get("ownership_type") or "").strip() or None,
            min_rank=c.get("min_rank") if isinstance(c.get("min_rank"), int) else None,
            max_rank=c.get("max_rank") if isinstance(c.get("max_rank"), int) else None,
        )
        db.add(item)
        saved += 1
    db.commit()

    return {
        "message": f"{saved} کدرشته از PDF استخراج و ذخیره شد" + (f" ({skipped} ردیف نامعتبر رد شد)." if skipped else "."),
        "saved_count": saved, "skipped_count": skipped,
    }


@router.get("/api/major-selection/admin-requests", dependencies=[Depends(require_admin)])
def list_major_selection_requests(db: Session = Depends(get_db)):
    rows = (
        db.query(models.MajorSelectionRequest)
        .order_by(models.MajorSelectionRequest.created_at.desc())
        .limit(200)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id, "full_name": r.full_name, "grade": r.grade,
                "konkur_rank": r.konkur_rank, "target_field": r.target_field,
                "target_city": r.target_city,
            }
            for r in rows
        ]
    }
