"""ابزار مشترک استخراج متن از فایل PDF (برای بانک سوالات و انتخاب رشته)."""
import io

from fastapi import HTTPException

DEFAULT_MAX_PDF_PAGES = 60


def extract_pdf_text(content: bytes, max_pages: int = DEFAULT_MAX_PDF_PAGES) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise HTTPException(status_code=500, detail="کتابخانه خواندن PDF روی سرور نصب نیست (pypdf).")

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="فایل PDF قابل خواندن نیست یا خراب است.")

    texts = []
    for page in reader.pages[:max_pages]:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(texts).strip()
