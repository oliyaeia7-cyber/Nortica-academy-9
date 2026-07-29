"""
تولید خروجی PDF فارسی (راست‌به‌چپ) برای برنامه مطالعاتی.
از reportlab برای ساخت PDF و از arabic_reshaper + python-bidi برای
شکل‌دهی درست حروف فارسی/عربی استفاده می‌شود (چون reportlab به‌صورت
پیش‌فرض حروف فارسی را به‌هم‌چسبیده و جهت‌دار نمایش نمی‌دهد).
"""
import os
import io
import urllib.request

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

import arabic_reshaper
from bidi.algorithm import get_display

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_REGULAR_PATH = os.path.join(FONT_DIR, "Vazirmatn-Regular.ttf")
FONT_BOLD_PATH = os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf")

FONT_URLS = {
    FONT_REGULAR_PATH: "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf",
    FONT_BOLD_PATH: "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Bold.ttf",
}

FONT_NAME = "Vazirmatn"
FONT_NAME_BOLD = "Vazirmatn-Bold"

_fonts_ready = False


def _ensure_fonts():
    """در صورت نبود فونت فارسی روی دیسک، آن را دانلود و رجیستر می‌کند.
    اگر دانلود ممکن نبود، از فونت پیش‌فرض Helvetica استفاده می‌شود
    (در این حالت حروف فارسی ممکن است درست نمایش داده نشوند)."""
    global _fonts_ready
    if _fonts_ready:
        return

    os.makedirs(FONT_DIR, exist_ok=True)
    for path, url in FONT_URLS.items():
        if not os.path.exists(path):
            try:
                urllib.request.urlretrieve(url, path)
            except Exception:
                pass

    try:
        if os.path.exists(FONT_REGULAR_PATH):
            pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_REGULAR_PATH))
        if os.path.exists(FONT_BOLD_PATH):
            pdfmetrics.registerFont(TTFont(FONT_NAME_BOLD, FONT_BOLD_PATH))
    except Exception:
        pass

    _fonts_ready = True


def _active_font():
    _ensure_fonts()
    if os.path.exists(FONT_REGULAR_PATH):
        return FONT_NAME
    return "Helvetica"


def _active_font_bold():
    _ensure_fonts()
    if os.path.exists(FONT_BOLD_PATH):
        return FONT_NAME_BOLD
    return "Helvetica-Bold"


def fa(text):
    """متن فارسی را برای نمایش درست راست‌به‌چپ در PDF آماده می‌کند."""
    if text is None:
        return ""
    text = str(text)
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


def build_plan_pdf(plan: dict) -> bytes:
    _ensure_fonts()
    font_name = _active_font()
    font_bold = _active_font_bold()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )

    title_style = ParagraphStyle(
        "TitleFa", fontName=font_bold, fontSize=18, alignment=TA_CENTER,
        textColor=colors.HexColor("#7c3aed"), spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "HeadingFa", fontName=font_bold, fontSize=13, alignment=TA_RIGHT,
        textColor=colors.HexColor("#201a3a"), spaceBefore=14, spaceAfter=6,
    )
    normal_style = ParagraphStyle(
        "NormalFa", fontName=font_name, fontSize=10.5, alignment=TA_RIGHT,
        textColor=colors.HexColor("#201a3a"), leading=16,
    )
    cell_style = ParagraphStyle(
        "CellFa", fontName=font_name, fontSize=9.5, alignment=TA_RIGHT, leading=14,
    )
    cell_style_bold = ParagraphStyle(
        "CellFaBold", fontName=font_bold, fontSize=9.5, alignment=TA_CENTER,
        textColor=colors.white, leading=14,
    )

    story = []
    story.append(Paragraph(fa("برنامه تحصیلی نورتیکا"), title_style))
    story.append(Paragraph(
        fa(f"پایه: {plan.get('grade', '')} — رشته: {plan.get('field', '')} — بازه: {plan.get('start_date', '')} تا {plan.get('end_date', '')}"),
        normal_style,
    ))
    story.append(Spacer(1, 8))

    if plan.get("analysis"):
        story.append(Paragraph(fa("تحلیل و توصیه هوش مصنوعی نورتیکا"), heading_style))
        story.append(Paragraph(fa(plan["analysis"]), normal_style))

    dist = plan.get("subject_distribution") or []
    if dist:
        story.append(Paragraph(fa("توزیع دروس در برنامه"), heading_style))
        data = [[Paragraph(fa("درصد"), cell_style_bold), Paragraph(fa("درس"), cell_style_bold)]]
        for d in dist:
            data.append([
                Paragraph(fa(f"{d.get('percent', 0)}٪"), cell_style),
                Paragraph(fa(d.get("subject", "")), cell_style),
            ])
        t = Table(data, colWidths=[40 * mm, 110 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c3aed")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8d0f0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f5ff")]),
        ]))
        story.append(t)

    growth = plan.get("growth_table") or []
    if growth:
        story.append(Paragraph(fa("جدول رشد پیش‌بینی‌شده"), heading_style))
        data = [[
            Paragraph(fa("توضیح"), cell_style_bold),
            Paragraph(fa("درصد تسلط"), cell_style_bold),
            Paragraph(fa("هفته"), cell_style_bold),
        ]]
        for g in growth:
            data.append([
                Paragraph(fa(g.get("note", "")), cell_style),
                Paragraph(fa(f"{g.get('expected_mastery_percent', 0)}٪"), cell_style),
                Paragraph(fa(str(g.get("week", ""))), cell_style),
            ])
        t = Table(data, colWidths=[80 * mm, 35 * mm, 35 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ec4899")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f4d6e6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff5fa")]),
        ]))
        story.append(t)

    schedule = plan.get("schedule") or []
    if schedule:
        story.append(Paragraph(fa("برنامه تحصیلی نورتیکا — جدول روزانه"), heading_style))

        # -------------------------------------------------------------
        # جمع‌آوری لیست دروس یکتا (به ترتیب اولین ظهور) و پیوت جدول به
        # شکل «هر ردیف یک روز، هر ستون یک درس» شبیه جدول‌های برنامه‌ریزی رایج
        # -------------------------------------------------------------
        subject_order = []
        for day in schedule:
            for it in (day.get("items") or []):
                name = it.get("subject", "")
                if name and name not in subject_order:
                    subject_order.append(name)
        if not subject_order:
            subject_order = ["برنامه"]

        palette = [
            colors.HexColor("#7c3aed"), colors.HexColor("#ec4899"), colors.HexColor("#f59e0b"),
            colors.HexColor("#16a34a"), colors.HexColor("#0ea5e9"), colors.HexColor("#dc2626"),
            colors.HexColor("#9333ea"), colors.HexColor("#0891b2"),
        ]

        day_col_style = ParagraphStyle(
            "DayColFa", fontName=font_bold, fontSize=8.5, alignment=TA_CENTER,
            textColor=colors.HexColor("#201a3a"), leading=11,
        )
        subj_cell_style = ParagraphStyle(
            "SubjCellFa", fontName=font_name, fontSize=7.5, alignment=TA_CENTER, leading=10,
        )
        subj_header_style = ParagraphStyle(
            "SubjHeaderFa", fontName=font_bold, fontSize=8, alignment=TA_CENTER,
            textColor=colors.white, leading=11,
        )

        header_row = [Paragraph(fa("روز / تاریخ"), cell_style_bold)] + [
            Paragraph(fa(s), subj_header_style) for s in subject_order
        ]
        data = [header_row]

        for day in schedule:
            items = day.get("items") or []
            if not items:
                continue
            by_subject = {}
            for it in items:
                name = it.get("subject", "")
                minutes = it.get("minutes", 0)
                focus = it.get("focus", "")
                entry = by_subject.setdefault(name, {"minutes": 0, "focus": []})
                entry["minutes"] += minutes or 0
                if focus and focus not in entry["focus"]:
                    entry["focus"].append(focus)

            date_label = day.get("date") or f"روز {day.get('day', '')}"
            day_name = day.get("day_name") or day.get("type") or ""
            date_cell_txt = fa(date_label) + ("<br/>" + fa(day_name) if day_name else "")
            row = [Paragraph(date_cell_txt, day_col_style)]
            for s in subject_order:
                if s in by_subject:
                    e = by_subject[s]
                    topic_txt = "، ".join(e["focus"][:2])
                    subj_cell_txt = fa(f"⏱ {e['minutes']} دقیقه")
                    if topic_txt:
                        subj_cell_txt += "<br/>" + fa(topic_txt)
                    row.append(Paragraph(subj_cell_txt, subj_cell_style))
                else:
                    row.append(Paragraph(fa("—"), subj_cell_style))
            data.append(row)

        usable_width = 174 * mm
        day_col_width = 30 * mm
        subj_col_width = max(16 * mm, (usable_width - day_col_width) / max(1, len(subject_order)))
        col_widths = [day_col_width] + [subj_col_width] * len(subject_order)

        t = Table(data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#201a3a")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8d0f0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f5ff")]),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        for i in range(len(subject_order)):
            col_idx = i + 1
            color = palette[i % len(palette)]
            style_cmds.append(("BACKGROUND", (col_idx, 0), (col_idx, 0), color))
        t.setStyle(TableStyle(style_cmds))
        story.append(t)

    story.append(Spacer(1, 14))
    story.append(Paragraph(fa("نورتیکا، نوری در مسیر تاریکی تو!"), normal_style))

    doc.build(story)
    return buffer.getvalue()


def build_major_selection_pdf(request_data: dict, candidates: list, result_text: str) -> bytes:
    """PDF نتیجه «انتخاب رشته هوشمند نورتیکا» شامل اطلاعات دانش‌آموز، تحلیل
    متنی و جدول کدرشته‌های پیشنهادی."""
    _ensure_fonts()
    font_name = _active_font()
    font_bold = _active_font_bold()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )

    title_style = ParagraphStyle(
        "TitleFa2", fontName=font_bold, fontSize=18, alignment=TA_CENTER,
        textColor=colors.HexColor("#7c3aed"), spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "HeadingFa2", fontName=font_bold, fontSize=13, alignment=TA_RIGHT,
        textColor=colors.HexColor("#201a3a"), spaceBefore=14, spaceAfter=6,
    )
    normal_style = ParagraphStyle(
        "NormalFa2", fontName=font_name, fontSize=10.5, alignment=TA_RIGHT,
        textColor=colors.HexColor("#201a3a"), leading=16,
    )
    cell_style = ParagraphStyle(
        "CellFa2", fontName=font_name, fontSize=8.5, alignment=TA_RIGHT, leading=12,
    )
    cell_style_bold = ParagraphStyle(
        "CellFaBold2", fontName=font_bold, fontSize=8.5, alignment=TA_CENTER,
        textColor=colors.white, leading=12,
    )

    story = [Paragraph(fa("انتخاب رشته هوشمند نورتیکا"), title_style)]

    info_lines = [
        f"نام: {request_data.get('full_name', '')} — پایه: {request_data.get('grade', '')} — "
        f"نمره دیپلم: {request_data.get('diploma_rank', '-')} — رتبه کنکور: {request_data.get('konkur_rank', '-')}",
        f"رشته مورد نظر: {request_data.get('target_field', '')} — شهر مورد نظر: {request_data.get('target_city', '') or 'بدون محدودیت'}",
    ]
    story.append(Paragraph("<br/>".join(fa(l) for l in info_lines), normal_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph(fa("تحلیل و توصیه"), heading_style))
    for line in (result_text or "").split("\n"):
        if line.strip():
            story.append(Paragraph(fa(line.strip()), normal_style))
    story.append(Spacer(1, 12))

    if candidates:
        story.append(Paragraph(fa(f"جدول کدرشته‌های پیشنهادی ({len(candidates)} مورد)"), heading_style))
        header = [
            Paragraph(fa("رتبه لازم"), cell_style_bold),
            Paragraph(fa("نوع"), cell_style_bold),
            Paragraph(fa("شهر"), cell_style_bold),
            Paragraph(fa("رشته"), cell_style_bold),
            Paragraph(fa("دانشگاه"), cell_style_bold),
            Paragraph(fa("کد"), cell_style_bold),
        ]
        data = [header]
        for c in candidates:
            rank_txt = ""
            if c.get("min_rank") or c.get("max_rank"):
                rank_txt = f"{c.get('min_rank', '')}-{c.get('max_rank', '')}"
            data.append([
                Paragraph(fa(rank_txt), cell_style),
                Paragraph(fa(c.get("ownership_type", "")), cell_style),
                Paragraph(fa(c.get("city", "")), cell_style),
                Paragraph(fa(c.get("major_name", "")), cell_style),
                Paragraph(fa(c.get("university_name", "")), cell_style),
                Paragraph(fa(c.get("code", "") or "-"), cell_style),
            ])
        col_widths = [22 * mm, 22 * mm, 22 * mm, 40 * mm, 50 * mm, 22 * mm]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c3aed")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8d0f0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f5ff")]),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(t)

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        fa("⚠️ این پیشنهادها بر پایه اطلاعات موجود و تحلیل هوش مصنوعی است و جایگزین دفترچه رسمی سازمان سنجش نیست؛ برای تصمیم نهایی حتماً دفترچه رسمی را نیز بررسی کنید."),
        normal_style,
    ))
    story.append(Paragraph(fa("نورتیکا، نوری در مسیر تاریکی تو!"), normal_style))

    doc.build(story)
    return buffer.getvalue()
