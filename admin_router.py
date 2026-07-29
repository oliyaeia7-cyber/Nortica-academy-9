import os
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from database import get_db
import models
from admin_auth import (
    ADMIN_PASSWORD,
    COOKIE_NAME,
    TOKEN_TTL_SECONDS,
    create_session_token,
    is_logged_in,
)

router = APIRouter(tags=["admin-panel"])

# ---------------------------------------------------------------------------
# استایل پنل ادمین به سبک وردپرس: سایدبار ثابت سمت راست + محتوای اصلی
# ---------------------------------------------------------------------------
_STYLE = """
<style>
  *{box-sizing:border-box;}
  body{font-family:Tahoma,sans-serif;background:#f0f0f1;color:#1d2327;direction:rtl;margin:0;}
  a{color:#a78bfa;text-decoration:none;}
  a:hover{text-decoration:underline;}

  .wp-shell{display:flex;min-height:100vh;}

  /* --------------------------- سایدبار --------------------------- */
  .wp-sidebar{width:220px;flex-shrink:0;background:#1d2327;color:#f0f0f1;min-height:100vh;padding:0;}
  .wp-brand{padding:18px 16px;font-size:1.05rem;font-weight:800;border-bottom:1px solid #2c3338;
    background:linear-gradient(90deg,#a78bfa,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
  .wp-menu{list-style:none;margin:0;padding:8px 0;}
  .wp-menu li{margin:0;}
  .wp-menu button.menu-link{width:100%;text-align:right;background:transparent;border:none;border-radius:0;
    color:#c3c4c7;padding:11px 16px;font-size:.9rem;display:flex;align-items:center;gap:10px;cursor:pointer;}
  .wp-menu button.menu-link:hover{background:#2c3338;color:#fff;}
  .wp-menu button.menu-link.active{background:#2c3338;color:#fff;border-right:3px solid #f472b6;padding-right:13px;}
  .menu-icon{font-size:1.05rem;}
  .wp-sidebar .view-site{display:block;padding:14px 16px;font-size:.8rem;color:#8c8f94;border-top:1px solid #2c3338;margin-top:10px;}

  /* --------------------------- محتوای اصلی --------------------------- */
  .wp-main{flex:1;min-width:0;}
  .wp-topbar{background:#fff;border-bottom:1px solid #dcdcde;padding:14px 26px;display:flex;
    justify-content:space-between;align-items:center;position:sticky;top:0;z-index:5;}
  .wp-topbar h1{font-size:1.15rem;margin:0;}
  .wp-topbar .logout-link{background:#f6f7f7;border:1px solid #dcdcde;padding:6px 16px;border-radius:6px;color:#1d2327;font-size:.82rem;}
  .wp-content{padding:24px 26px 60px;max-width:1100px;}

  .wp-panel{display:none;}
  .wp-panel.active{display:block;}

  /* --------------------------- کارت‌ها و فرم‌ها --------------------------- */
  .card{background:#fff;border:1px solid #dcdcde;border-radius:8px;padding:20px;margin-bottom:18px;box-shadow:0 1px 1px rgba(0,0,0,.02);}
  .card h3{margin-top:0;font-size:1rem;}
  label{display:block;font-size:.82rem;color:#50575e;margin-bottom:6px;font-weight:600;}
  input,textarea,select{width:100%;padding:9px 12px;border-radius:6px;border:1px solid #8c8f94;
    background:#fff;color:#1d2327;font-family:inherit;box-sizing:border-box;margin-bottom:14px;font-size:.88rem;}
  input:focus,textarea:focus,select:focus{outline:none;border-color:#a78bfa;}
  button{cursor:pointer;border:none;padding:9px 20px;border-radius:6px;font-weight:700;
    background:linear-gradient(90deg,#a78bfa,#f472b6);color:#fff;font-size:.85rem;}
  button.danger{background:#d63638;}
  button.secondary{background:#fff;border:1px solid #a78bfa;color:#a78bfa;}
  button.small{padding:5px 13px;font-size:.78rem;}
  .row{display:flex;gap:10px;flex-wrap:wrap;}
  .post-title{margin:0 0 6px;}
  .error{background:#fcf0f1;border-right:4px solid #d63638;color:#d63638;padding:10px 14px;border-radius:6px;margin-bottom:14px;font-size:.85rem;}
  .success{background:#edfaef;border-right:4px solid #00a32a;color:#00a32a;padding:10px 14px;border-radius:6px;margin-bottom:14px;font-size:.85rem;}
  .thumb{width:100%;max-height:160px;object-fit:cover;border-radius:6px;margin-bottom:10px;}
  .muted{color:#787c82;}

  /* --------------------------- داشبورد آماری --------------------------- */
  .stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:22px;}
  .stat-card{background:#fff;border:1px solid #dcdcde;border-radius:8px;padding:18px;text-align:center;}
  .stat-card .num{font-size:1.7rem;font-weight:800;background:linear-gradient(90deg,#a78bfa,#f472b6);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
  .stat-card .lbl{font-size:.8rem;color:#787c82;margin-top:4px;}
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
  @media (max-width:760px){.two-col{grid-template-columns:1fr;}.wp-sidebar{width:64px;}
    .wp-brand{font-size:0;padding:18px 8px;}.wp-menu button.menu-link span.label{display:none;}
    .wp-sidebar .view-site{display:none;}}

  /* --------------------------- مدیا و جدول‌ها --------------------------- */
  .media-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px;}
  .media-item{background:#f6f7f7;border:1px solid #dcdcde;border-radius:8px;padding:10px;}
  .media-item img{width:100%;height:100px;object-fit:cover;border-radius:6px;margin-bottom:8px;}
  .media-item .url-box{font-size:.7rem;color:#787c82;word-break:break-all;margin-bottom:8px;}
  table{width:100%;border-collapse:collapse;font-size:.85rem;background:#fff;}
  th,td{padding:10px;text-align:right;border-bottom:1px solid #f0f0f1;}
  th{color:#787c82;font-weight:700;background:#f6f7f7;}
  .status-badge{padding:3px 10px;border-radius:999px;font-size:.72rem;background:#f0e9ff;color:#7c3aed;}
  .list-item{padding:9px 0;border-bottom:1px solid #f0f0f1;font-size:.85rem;}
  .list-item:last-child{border-bottom:none;}
</style>
"""


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request, error: str = ""):
    if is_logged_in(request):
        return RedirectResponse(url="/admin")
    error_html = f'<div class="error">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl"><head><meta charset="UTF-8"><title>ورود ادمین | نورتیکا</title>{_STYLE}</head>
<body><div class="wp-content" style="max-width:360px;margin:80px auto 0;">
  <div class="card">
    <h1 style="font-size:1.2rem;">ورود به پنل ادمین</h1>
    {error_html}
    <form method="post" action="/admin/login">
      <label>رمز عبور</label>
      <input type="password" name="password" required autofocus />
      <button type="submit" style="width:100%;">ورود</button>
    </form>
  </div>
</div></body></html>"""


@router.post("/admin/login")
def admin_login_submit(password: str = Form(...)):
    if not ADMIN_PASSWORD or password != ADMIN_PASSWORD:
        return RedirectResponse(url="/admin/login?error=رمز+عبور+اشتباه+است", status_code=303)
    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        create_session_token(),
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=TOKEN_TTL_SECONDS,
    )
    return resp


@router.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse(url="/admin/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/admin/backup-db")
def admin_backup_db(request: Request):
    """دانلود نسخه پشتیبان دیتابیس محلی SQLite (فقط زمانی که DATABASE_URL تنظیم
    نشده و پروژه به‌صورت محلی/بدون PostgreSQL اجرا می‌شود). وقتی یک دیتابیس
    PostgreSQL پایدار (طبق render.yaml) وصل باشد، این فایل اصلاً وجود ندارد
    چون داده‌ها مستقیماً و همیشگی در PostgreSQL ذخیره می‌شوند."""
    if not is_logged_in(request):
        return RedirectResponse(url="/admin/login")

    db_path = os.path.join("data", "noortika.db")
    if not os.path.exists(db_path):
        return HTMLResponse(
            "<h3 style='font-family:Tahoma;direction:rtl;'>"
            "این سایت الان از یک دیتابیس PostgreSQL پایدار استفاده می‌کند، نه فایل SQLite محلی؛ "
            "پس داده‌ها همیشگی هستند و نیازی به دانلود نسخه پشتیبان از این مسیر نیست. "
            "برای پشتیبان‌گیری از PostgreSQL، از داشبورد Render (بخش دیتابیس > Backups) استفاده کنید."
            "</h3>",
            status_code=404,
        )

    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M")
    return FileResponse(
        db_path,
        media_type="application/octet-stream",
        filename=f"noortika-backup-{timestamp}.db",
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    if not is_logged_in(request):
        return RedirectResponse(url="/admin/login")

    # -------------------- آمار داشبورد --------------------
    posts = db.query(models.BlogPost).order_by(models.BlogPost.created_at.desc()).all()
    media_count = db.query(models.MediaAsset).count()
    links_count = db.query(models.SiteLink).count()
    tickets = db.query(models.SupportTicket).order_by(models.SupportTicket.created_at.desc()).all()
    open_tickets_count = sum(1 for t in tickets if t.status != "بسته شد")
    users_count = db.query(models.User).count()

    recent_posts_html = "".join(
        f'<div class="list-item"><a href="/blog/{p.slug}" target="_blank">{p.title}</a></div>'
        for p in posts[:5]
    ) or '<p class="muted">هنوز مقاله‌ای اضافه نشده.</p>'

    recent_tickets_html = "".join(
        f'<div class="list-item">{t.subject} — <span class="status-badge">{t.status}</span></div>'
        for t in tickets[:5]
    ) or '<p class="muted">تیکتی ثبت نشده.</p>'

    # -------------------- ردیف‌های مقالات وبلاگ --------------------
    post_rows = "".join(
        f"""
  <div class="card post-row" data-slug="{p.slug}">
    {f'<img class="thumb" src="{p.image_url}" alt="{p.title}"/>' if p.image_url else ""}
    <h3 class="post-title">{p.title}</h3>
    <p class="muted">{p.description}</p>
    <div class="row">
      <a href="/blog/{p.slug}" target="_blank">مشاهده در سایت</a>
      {f'<a href="{p.link_url}" target="_blank">لینک مرتبط</a>' if p.link_url else ""}
    </div>
    <div class="row" style="margin-top:10px;">
      <button type="button" class="secondary small edit-btn">ویرایش</button>
      <button type="button" class="danger small delete-btn">حذف</button>
    </div>
  </div>"""
        for p in posts
    )
    if not post_rows:
        post_rows = '<p class="muted">هنوز مقاله‌ای اضافه نشده.</p>'

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl"><head><meta charset="UTF-8"><title>پنل ادمین | نورتیکا</title>{_STYLE}</head>
<body>
<div class="wp-shell">

  <!-- ===================== سایدبار ===================== -->
  <aside class="wp-sidebar">
    <div class="wp-brand">نورتیکا ادمین</div>
    <ul class="wp-menu">
      <li><button class="menu-link active" data-tab="dashboard"><span class="menu-icon">📊</span><span class="label">داشبورد</span></button></li>
      <li><button class="menu-link" data-tab="blog"><span class="menu-icon">📝</span><span class="label">وبلاگ / مقالات</span></button></li>
      <li><button class="menu-link" data-tab="media"><span class="menu-icon">🖼️</span><span class="label">کتابخانه رسانه</span></button></li>
      <li><button class="menu-link" data-tab="links"><span class="menu-icon">🔗</span><span class="label">لینک‌ها</span></button></li>
      <li><button class="menu-link" data-tab="tickets"><span class="menu-icon">🎫</span><span class="label">تیکت‌های پشتیبانی</span></button></li>
      <li><button class="menu-link" data-tab="users"><span class="menu-icon">👥</span><span class="label">کاربران</span></button></li>
      <li><button class="menu-link" data-tab="questions"><span class="menu-icon">🧠</span><span class="label">بانک سوالات آزمون</span></button></li>
      <li><button class="menu-link" data-tab="consultations"><span class="menu-icon">💬</span><span class="label">مشاوره‌های دانش‌آموزان</span></button></li>
      <li><button class="menu-link" data-tab="majorcodes"><span class="menu-icon">🎓</span><span class="label">انتخاب رشته (کدرشته‌ها)</span></button></li>
      <li><button class="menu-link" data-tab="pricing"><span class="menu-icon">💰</span><span class="label">قیمت‌گذاری</span></button></li>
    </ul>
    <a class="view-site" href="/" target="_blank">↗ مشاهده سایت</a>
  </aside>

  <!-- ===================== محتوای اصلی ===================== -->
  <main class="wp-main">
    <div class="wp-topbar">
      <h1 id="panel-title">داشبورد</h1>
      <div class="row" style="gap:10px;">
        <a class="logout-link" href="/admin/backup-db">⬇ دانلود بکاپ دیتابیس</a>
        <a class="logout-link" href="/admin/logout">خروج</a>
      </div>
    </div>

    <div class="wp-content">

      <!-- ===================== داشبورد ===================== -->
      <div class="wp-panel active" id="tab-dashboard">
        <div class="stat-grid">
          <div class="stat-card"><div class="num">{len(posts)}</div><div class="lbl">مقاله وبلاگ</div></div>
          <div class="stat-card"><div class="num">{media_count}</div><div class="lbl">فایل رسانه</div></div>
          <div class="stat-card"><div class="num">{links_count}</div><div class="lbl">لینک سایت</div></div>
          <div class="stat-card"><div class="num">{open_tickets_count}</div><div class="lbl">تیکت باز</div></div>
          <div class="stat-card"><div class="num">{users_count}</div><div class="lbl">کاربر ثبت‌نامی</div></div>
        </div>
        <div class="two-col">
          <div class="card">
            <h3>آخرین مقالات</h3>
            {recent_posts_html}
          </div>
          <div class="card">
            <h3>آخرین تیکت‌ها</h3>
            {recent_tickets_html}
          </div>
        </div>
      </div>

      <!-- ===================== وبلاگ ===================== -->
      <div class="wp-panel" id="tab-blog">
        <div class="card">
          <h3>افزودن مقاله جدید</h3>
          <div id="blog-alert-box"></div>
          <form id="add-form">
            <label>تیتر مقاله</label>
            <input type="text" id="a_title" required />
            <label>توضیحات مقاله</label>
            <textarea id="a_description" rows="6" required></textarea>
            <label>تصویر کاور (اختیاری)</label>
            <div class="row" style="align-items:center;margin-bottom:14px;">
              <input type="file" id="a_image_file" accept="image/*" style="flex:1;margin-bottom:0;" />
              <button type="button" class="secondary small" id="a_upload_btn">آپلود تصویر</button>
            </div>
            <input type="hidden" id="a_image_url" />
            <div id="a_image_preview"></div>
            <label>لینک مرتبط (اختیاری)</label>
            <input type="url" id="a_link_url" placeholder="https://example.com" />
            <button type="submit">ذخیره مقاله</button>
          </form>
        </div>

        <h3>مقالات ثبت‌شده</h3>
        {post_rows}
      </div>

      <!-- ===================== رسانه ===================== -->
      <div class="wp-panel" id="tab-media">
        <div class="card">
          <h3>آپلود تصویر جدید</h3>
          <div id="media-alert-box"></div>
          <div class="row" style="align-items:center;">
            <input type="file" id="media_upload_file" accept="image/*" style="flex:1;margin-bottom:0;" />
            <button type="button" id="media_upload_btn">آپلود</button>
          </div>
        </div>
        <div class="card">
          <h3>تصاویر آپلودشده</h3>
          <div class="media-grid" id="media-grid">در حال بارگذاری...</div>
        </div>
      </div>

      <!-- ===================== لینک‌ها ===================== -->
      <div class="wp-panel" id="tab-links">
        <div class="card">
          <h3>افزودن لینک جدید</h3>
          <div id="links-alert-box"></div>
          <form id="link-form">
            <label>عنوان لینک</label>
            <input type="text" id="l_title" required />
            <label>آدرس لینک</label>
            <input type="url" id="l_url" required placeholder="https://example.com" />
            <label>اولویت نمایش (عدد کوچیک‌تر = جلوتر)</label>
            <input type="number" id="l_position" value="0" />
            <button type="submit">ذخیره لینک</button>
          </form>
        </div>
        <div class="card">
          <h3>لینک‌های ثبت‌شده</h3>
          <div id="links-list">در حال بارگذاری...</div>
        </div>
      </div>

      <!-- ===================== تیکت‌ها ===================== -->
      <div class="wp-panel" id="tab-tickets">
        <div class="card">
          <h3>اطلاعات تماس پشتیبانی</h3>
          <p class="muted" style="font-size:.82rem;">این مقادیر پیش‌فرض خالی هستند و فقط در صورت پرکردن، در صفحه پشتیبانی سایت نمایش داده می‌شوند.</p>
          <div id="contact-alert-box"></div>
          <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div class="field">
              <label>آدرس محل کار</label>
              <div style="display:flex;gap:6px;">
                <input type="text" id="ci_office_address" placeholder="خالی" />
                <button type="button" class="secondary small" data-clear-field="office_address">حذف</button>
              </div>
            </div>
            <div class="field">
              <label>تلفن شرکت</label>
              <div style="display:flex;gap:6px;">
                <input type="text" id="ci_company_phone" placeholder="خالی" />
                <button type="button" class="secondary small" data-clear-field="company_phone">حذف</button>
              </div>
            </div>
            <div class="field">
              <label>آدرس کانال تلگرام</label>
              <div style="display:flex;gap:6px;">
                <input type="text" id="ci_telegram_channel" placeholder="خالی" />
                <button type="button" class="secondary small" data-clear-field="telegram_channel">حذف</button>
              </div>
            </div>
            <div class="field">
              <label>آدرس کانال بله</label>
              <div style="display:flex;gap:6px;">
                <input type="text" id="ci_bale_channel" placeholder="خالی" />
                <button type="button" class="secondary small" data-clear-field="bale_channel">حذف</button>
              </div>
            </div>
            <div class="field">
              <label>آدرس اینستاگرام</label>
              <div style="display:flex;gap:6px;">
                <input type="text" id="ci_instagram_channel" placeholder="خالی" />
                <button type="button" class="secondary small" data-clear-field="instagram_channel">حذف</button>
              </div>
            </div>
          </div>
          <button type="button" id="contact-save-btn" class="small" style="margin-top:10px;">ذخیره اطلاعات تماس</button>
        </div>
        <div class="card">
          <h3>تیکت‌های پشتیبانی</h3>
          <div id="tickets-alert-box"></div>
          <div id="tickets-list">در حال بارگذاری...</div>
        </div>
      </div>

      <!-- ===================== کاربران ===================== -->
      <div class="wp-panel" id="tab-users">
        <div class="card">
          <h3>کاربران ثبت‌نامی</h3>
          <div id="users-list">در حال بارگذاری...</div>
        </div>
      </div>

      <!-- ===================== بانک سوالات آزمون ===================== -->
      <div class="wp-panel" id="tab-questions">
        <div class="card">
          <h3>افزودن سوال جدید به بانک سوالات</h3>
          <p class="muted" style="font-size:.82rem;">سوالاتی که اینجا اضافه می‌کنی، در آزمون‌های واقعی سایت در اولویت انتخاب هستند (به‌جای تولید خودکار).</p>
          <div id="qb-alert-box"></div>
          <form id="qb-form">
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>پایه تحصیلی</label>
                <select id="qb_grade" required></select>
              </div>
              <div class="field">
                <label>درس</label>
                <input type="text" id="qb_subject" list="qb_subject_list" required placeholder="مثلاً ریاضی دهم" />
                <datalist id="qb_subject_list"></datalist>
              </div>
            </div>
            <label>فصل / مبحث (اختیاری)</label>
            <input type="text" id="qb_lesson" placeholder="مثلاً بردار و مختصات" />
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>سطح سختی</label>
                <select id="qb_difficulty">
                  <option>آسان</option>
                  <option selected>متوسط</option>
                  <option>سخت</option>
                </select>
              </div>
              <div class="field">
                <label>نوع سوال</label>
                <select id="qb_type">
                  <option value="تستی" selected>تستی (چهارگزینه‌ای)</option>
                  <option value="تشریحی">تشریحی</option>
                </select>
              </div>
            </div>
            <label>متن سوال</label>
            <textarea id="qb_question_text" rows="3" required></textarea>

            <div id="qb-mcq-fields">
              <label>گزینه ۱</label>
              <input type="text" id="qb_opt0" />
              <label>گزینه ۲</label>
              <input type="text" id="qb_opt1" />
              <label>گزینه ۳</label>
              <input type="text" id="qb_opt2" />
              <label>گزینه ۴</label>
              <input type="text" id="qb_opt3" />
              <label>گزینه صحیح</label>
              <select id="qb_correct_index">
                <option value="0">گزینه ۱</option>
                <option value="1">گزینه ۲</option>
                <option value="2">گزینه ۳</option>
                <option value="3">گزینه ۴</option>
              </select>
            </div>
            <div id="qb-essay-fields" style="display:none;">
              <label>پاسخ نمونه (کامل و صحیح)</label>
              <textarea id="qb_model_answer" rows="3"></textarea>
            </div>

            <button type="submit" style="margin-top:6px;">افزودن به بانک سوالات</button>
          </form>
        </div>

        <div class="card">
          <h3>📄 آپلود PDF سوالات (استخراج خودکار با هوش مصنوعی)</h3>
          <p class="muted" style="font-size:.82rem;">یک فایل PDF شامل سوالات (تستی یا تشریحی) آپلود کن؛ هوش مصنوعی سوالات را از داخل فایل استخراج می‌کند و مستقیم به بانک سوالات اضافه می‌شوند. فایل باید متنی باشد (نه اسکن تصویری).</p>
          <div id="qb-pdf-alert-box"></div>
          <form id="qb-pdf-form">
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>پایه تحصیلی</label>
                <select id="qbp_grade" required></select>
              </div>
              <div class="field">
                <label>درس</label>
                <input type="text" id="qbp_subject" list="qb_subject_list" required placeholder="مثلاً ریاضی دهم" />
              </div>
            </div>
            <label>فصل / مبحث (اختیاری)</label>
            <input type="text" id="qbp_lesson" placeholder="مثلاً بردار و مختصات" />
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>سطح سختی سوالات فایل</label>
                <select id="qbp_difficulty">
                  <option>آسان</option>
                  <option selected>متوسط</option>
                  <option>سخت</option>
                </select>
              </div>
              <div class="field">
                <label>نوع سوالات فایل</label>
                <select id="qbp_type">
                  <option value="تستی" selected>تستی (چهارگزینه‌ای)</option>
                  <option value="تشریحی">تشریحی</option>
                </select>
              </div>
            </div>
            <label>فایل PDF سوالات</label>
            <input type="file" id="qbp_file" accept="application/pdf" required />
            <button type="submit" style="margin-top:6px;">استخراج و افزودن سوالات از PDF</button>
          </form>
        </div>

        <div class="card">
          <h3>🖼️ آپلود عکس یا PDF اسکن‌شده سوالات (استخراج تصویری با هوش مصنوعی)</h3>
          <p class="muted" style="font-size:.82rem;">عکس یا PDF اسکن‌شده/عکسی از برگه سوالات (تستی، تشریحی یا هر دو با هم) آپلود کن؛ هوش مصنوعی هم متن سوالات و هم پاسخ‌های نوشته‌شده در تصویر را می‌خواند و مستقیم به بانک سوالات اضافه می‌کند.</p>
          <div id="qb-image-alert-box"></div>
          <form id="qb-image-form">
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>پایه تحصیلی</label>
                <select id="qbi_grade" required></select>
              </div>
              <div class="field">
                <label>درس</label>
                <input type="text" id="qbi_subject" list="qb_subject_list" required placeholder="مثلاً ریاضی هشتم" />
              </div>
            </div>
            <label>فصل / مبحث (اختیاری)</label>
            <input type="text" id="qbi_lesson" placeholder="مثلاً معادله" />
            <label>سطح سختی سوالات فایل</label>
            <select id="qbi_difficulty">
              <option>آسان</option>
              <option selected>متوسط</option>
              <option>سخت</option>
            </select>
            <label>فایل عکس یا PDF</label>
            <input type="file" id="qbi_file" accept="image/*,application/pdf" required />
            <button type="submit" style="margin-top:6px;">استخراج سوال و پاسخ از عکس/PDF</button>
          </form>
        </div>

        <div class="card">
          <h3>فیلتر و مشاهده سوالات</h3>
          <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div class="field">
              <label>پایه</label>
              <select id="qb_filter_grade"><option value="">همه پایه‌ها</option></select>
            </div>
            <div class="field">
              <label>درس</label>
              <input type="text" id="qb_filter_subject" placeholder="مثلاً ریاضی دهم" />
            </div>
          </div>
          <button type="button" class="secondary small" id="qb_filter_btn">جست‌وجو</button>
          <div id="qb-list" style="margin-top:14px;">در حال بارگذاری...</div>
        </div>
      </div>

      <!-- ===================== مشاوره‌های دانش‌آموزان ===================== -->
      <div class="wp-panel" id="tab-consultations">
        <div class="card" id="consult-list-card">
          <h3>دانش‌آموزانی که با مشاوره هوشمند گفت‌وگو داشته‌اند</h3>
          <div id="consult-admin-list">در حال بارگذاری...</div>
        </div>
        <div class="card" id="consult-transcript-card" style="display:none;">
          <h3 id="consult-transcript-title">گفت‌وگو</h3>
          <button type="button" class="secondary small" id="consult-back-btn" style="margin-bottom:12px;">&rarr; بازگشت به لیست</button>
          <div id="consult-transcript"></div>
        </div>
      </div>

      <!-- ===================== انتخاب رشته (کدرشته‌ها) ===================== -->
      <div class="wp-panel" id="tab-majorcodes">
        <div class="card">
          <h3>افزودن کدرشته جدید</h3>
          <div id="mc-alert-box"></div>
          <form id="mc-form">
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>کد رشته (اختیاری)</label>
                <input type="text" id="mc_code" />
              </div>
              <div class="field">
                <label>نوع دانشگاه</label>
                <select id="mc_ownership">
                  <option>دولتی</option>
                  <option>آزاد</option>
                  <option>غیرانتفاعی</option>
                  <option>پیام نور</option>
                  <option>شبانه</option>
                </select>
              </div>
            </div>
            <label>نام دانشگاه</label>
            <input type="text" id="mc_university" required />
            <label>نام رشته</label>
            <input type="text" id="mc_major" required />
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>شهر</label>
                <input type="text" id="mc_city" />
              </div>
              <div class="field">
                <label>گروه آزمایشی</label>
                <select id="mc_field_group">
                  <option value="">-</option>
                  <option>ریاضی فیزیک</option>
                  <option>علوم تجربی</option>
                  <option>علوم انسانی</option>
                  <option>هنر</option>
                  <option>زبان</option>
                </select>
              </div>
            </div>
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>حداقل رتبه قبولی سال قبل</label>
                <input type="number" id="mc_min_rank" />
              </div>
              <div class="field">
                <label>حداکثر رتبه قبولی سال قبل</label>
                <input type="number" id="mc_max_rank" />
              </div>
            </div>
            <label>توضیحات (اختیاری)</label>
            <input type="text" id="mc_notes" />
            <button type="submit" style="margin-top:6px;">افزودن کدرشته</button>
          </form>
        </div>

        <div class="card">
          <h3>📄 آپلود دسته‌جمعی با CSV</h3>
          <p class="muted" style="font-size:.82rem;">فرمت ستون‌ها (ردیف اول = هدر): کد, دانشگاه, رشته, شهر, نوع, گروه, حداقل_رتبه, حداکثر_رتبه, توضیحات — روش دقیق‌تر و سریع‌تر برای دیتاست‌های بزرگ.</p>
          <div id="mc-csv-alert-box"></div>
          <input type="file" id="mc_csv_file" accept=".csv" />
          <button type="button" id="mc-csv-upload-btn" style="margin-top:8px;">آپلود CSV</button>
        </div>

        <div class="card">
          <h3>🧠 آپلود PDF دفترچه (استخراج خودکار با هوش مصنوعی)</h3>
          <p class="muted" style="font-size:.82rem;">اگر دفترچه یا فهرست کدرشته را فقط به‌صورت PDF داری، اینجا آپلودش کن؛ هوش مصنوعی کدرشته‌ها رو می‌خونه و به بانک اضافه می‌کنه. برای فایل‌های خیلی بزرگ (چند هزار ردیف)، فایل رو به چند بخش کوچک‌تر تقسیم کن و چندبار آپلود کن، یا از CSV استفاده کن (دقیق‌تره).</p>
          <div id="mc-pdf-alert-box"></div>
          <input type="file" id="mc_pdf_file" accept="application/pdf" />
          <button type="button" id="mc-pdf-upload-btn" style="margin-top:8px;">استخراج و افزودن از PDF</button>
        </div>

        <div class="card">
          <h3>جست‌وجو در کدرشته‌های ثبت‌شده</h3>
          <input type="text" id="mc_search" placeholder="نام دانشگاه، رشته، شهر یا کد..." />
          <button type="button" class="secondary small" id="mc-search-btn">جست‌وجو</button>
          <p class="muted" id="mc-total-count" style="font-size:.8rem;margin-top:8px;"></p>
          <div id="mc-list" style="margin-top:10px;">در حال بارگذاری...</div>
        </div>
      </div>

      <!-- ===================== قیمت‌گذاری ===================== -->
      <div class="wp-panel" id="tab-pricing">
        <div class="card">
          <h3>افزودن پلن جدید</h3>
          <div id="pr-alert-box"></div>
          <form id="pr-form">
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>شناسه پلن (plan_key — انگلیسی، بدون فاصله)</label>
                <input type="text" id="pr_plan_key" required placeholder="مثلاً month" />
              </div>
              <div class="field">
                <label>عنوان پلن</label>
                <input type="text" id="pr_title" required />
              </div>
            </div>
            <label>توضیحات</label>
            <input type="text" id="pr_description" />
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>قیمت (عدد، تومان)</label>
                <input type="number" id="pr_price" value="0" />
              </div>
              <div class="field">
                <label>برچسب قیمت (متنی که نمایش داده می‌شود)</label>
                <input type="text" id="pr_price_label" required placeholder="مثلاً ۵۰۰,۰۰۰ تومان" />
              </div>
            </div>
            <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="field">
                <label>مدت (duration، اختیاری)</label>
                <input type="text" id="pr_duration" placeholder="week / month / six_month / year" />
              </div>
              <div class="field">
                <label>اولویت نمایش (عدد کوچیک‌تر = جلوتر)</label>
                <input type="number" id="pr_position" value="0" />
              </div>
            </div>
            <button type="submit" style="margin-top:6px;">افزودن پلن</button>
          </form>
        </div>

        <div class="card">
          <h3>پلن‌های فعلی</h3>
          <div id="pr-list">در حال بارگذاری...</div>
        </div>
      </div>

    </div>
  </main>
</div>

<script>
const PANEL_TITLES = {{
  dashboard: "داشبورد",
  blog: "وبلاگ / مقالات",
  media: "کتابخانه رسانه",
  links: "لینک‌ها",
  tickets: "تیکت‌های پشتیبانی",
  users: "کاربران",
  questions: "بانک سوالات آزمون",
  consultations: "مشاوره‌های دانش‌آموزان",
  majorcodes: "انتخاب رشته (کدرشته‌ها)",
  pricing: "قیمت‌گذاری",
}};

async function apiCall(path, method, body) {{
  const res = await fetch(path, {{
    method,
    headers: {{ "Content-Type": "application/json" }},
    body: body ? JSON.stringify(body) : undefined,
  }});
  if (!res.ok) {{
    const err = await res.json().catch(() => ({{ detail: "خطای ناشناخته" }}));
    throw new Error(err.detail || "خطا در ارتباط با سرور");
  }}
  return res.json();
}}

async function uploadFile(path, file) {{
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(path, {{ method: "POST", body: fd }});
  if (!res.ok) {{
    const err = await res.json().catch(() => ({{ detail: "خطای ناشناخته" }}));
    throw new Error(err.detail || "خطا در آپلود");
  }}
  return res.json();
}}

document.querySelectorAll(".menu-link").forEach((btn) => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".menu-link").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".wp-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    document.getElementById("tab-" + tab).classList.add("active");
    document.getElementById("panel-title").textContent = PANEL_TITLES[tab] || "";
    if (tab === "media") loadMedia();
    if (tab === "links") loadLinks();
    if (tab === "tickets") {{ loadTickets(); loadContactInfo(); }}
    if (tab === "users") loadUsers();
    if (tab === "questions") initQuestionBankTab();
    if (tab === "consultations") loadConsultationsList();
    if (tab === "majorcodes") loadMajorCodes();
    if (tab === "pricing") loadPricingPlans();
  }});
}});

document.getElementById("a_upload_btn").addEventListener("click", async () => {{
  const fileInput = document.getElementById("a_image_file");
  const alertBox = document.getElementById("blog-alert-box");
  if (!fileInput.files[0]) {{
    alertBox.innerHTML = `<div class="error">اول یک تصویر انتخاب کن.</div>`;
    return;
  }}
  try {{
    const data = await uploadFile("/api/media/upload", fileInput.files[0]);
    document.getElementById("a_image_url").value = data.url;
    document.getElementById("a_image_preview").innerHTML =
      `<img class="thumb" src="${{data.url}}" alt="پیش‌نمایش" />`;
    alertBox.innerHTML = `<div class="success">تصویر آپلود شد.</div>`;
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

document.getElementById("add-form").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const alertBox = document.getElementById("blog-alert-box");
  try {{
    await apiCall("/api/blog", "POST", {{
      title: document.getElementById("a_title").value,
      description: document.getElementById("a_description").value,
      image_url: document.getElementById("a_image_url").value || null,
      link_url: document.getElementById("a_link_url").value || null,
    }});
    window.location.reload();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

document.querySelectorAll(".delete-btn").forEach((btn) => {{
  btn.addEventListener("click", async () => {{
    if (!confirm("این مقاله حذف بشه؟")) return;
    const slug = btn.closest(".post-row").dataset.slug;
    try {{
      await apiCall("/api/blog/" + slug, "DELETE");
      window.location.reload();
    }} catch (err) {{
      alert(err.message);
    }}
  }});
}});

document.querySelectorAll(".edit-btn").forEach((btn) => {{
  btn.addEventListener("click", () => {{
    const row = btn.closest(".post-row");
    const slug = row.dataset.slug;
    const currentTitle = row.querySelector(".post-title").textContent.trim();
    const currentDesc = row.querySelector("p").textContent.trim();
    row.innerHTML = `
      <label>تیتر مقاله</label>
      <input type="text" class="edit-title" value="${{currentTitle.replace(/"/g, "&quot;")}}" />
      <label>توضیحات مقاله</label>
      <textarea class="edit-desc" rows="6">${{currentDesc}}</textarea>
      <label>آدرس تصویر کاور (اختیاری)</label>
      <input type="text" class="edit-image" placeholder="/media/1" />
      <label>لینک مرتبط (اختیاری)</label>
      <input type="url" class="edit-link" placeholder="https://example.com" />
      <div class="row">
        <button type="button" class="save-btn">ذخیره</button>
        <button type="button" class="secondary cancel-btn">انصراف</button>
      </div>
    `;
    row.querySelector(".cancel-btn").addEventListener("click", () => window.location.reload());
    row.querySelector(".save-btn").addEventListener("click", async () => {{
      try {{
        await apiCall("/api/blog/" + slug, "PUT", {{
          title: row.querySelector(".edit-title").value,
          description: row.querySelector(".edit-desc").value,
          image_url: row.querySelector(".edit-image").value || null,
          link_url: row.querySelector(".edit-link").value || null,
        }});
        window.location.reload();
      }} catch (err) {{
        alert(err.message);
      }}
    }});
  }});
}});

document.getElementById("media_upload_btn").addEventListener("click", async () => {{
  const fileInput = document.getElementById("media_upload_file");
  const alertBox = document.getElementById("media-alert-box");
  if (!fileInput.files[0]) {{
    alertBox.innerHTML = `<div class="error">اول یک تصویر انتخاب کن.</div>`;
    return;
  }}
  try {{
    await uploadFile("/api/media/upload", fileInput.files[0]);
    alertBox.innerHTML = `<div class="success">آپلود شد.</div>`;
    fileInput.value = "";
    loadMedia();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

async function loadMedia() {{
  const grid = document.getElementById("media-grid");
  try {{
    const res = await fetch("/api/media");
    if (!res.ok) throw new Error("خطا در دریافت رسانه‌ها");
    const data = await res.json();
    if (!data.items.length) {{
      grid.innerHTML = '<p class="muted">هنوز تصویری آپلود نشده.</p>';
      return;
    }}
    grid.innerHTML = data.items
      .map(
        (m) => `
      <div class="media-item" data-id="${{m.id}}">
        <img src="${{m.url}}" alt="${{m.filename || ""}}" />
        <div class="url-box">${{m.url}}</div>
        <div class="row">
          <button type="button" class="secondary small copy-btn">کپی آدرس</button>
          <button type="button" class="danger small del-media-btn">حذف</button>
        </div>
      </div>`
      )
      .join("");

    grid.querySelectorAll(".copy-btn").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        const url = btn.closest(".media-item").querySelector(".url-box").textContent;
        navigator.clipboard.writeText(url);
        btn.textContent = "کپی شد!";
        setTimeout(() => (btn.textContent = "کپی آدرس"), 1200);
      }});
    }});
    grid.querySelectorAll(".del-media-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        if (!confirm("این تصویر حذف بشه؟")) return;
        const id = btn.closest(".media-item").dataset.id;
        try {{
          await apiCall("/api/media/" + id, "DELETE");
          loadMedia();
        }} catch (err) {{
          alert(err.message);
        }}
      }});
    }});
  }} catch (err) {{
    grid.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

document.getElementById("link-form").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const alertBox = document.getElementById("links-alert-box");
  try {{
    await apiCall("/api/links", "POST", {{
      title: document.getElementById("l_title").value,
      url: document.getElementById("l_url").value,
      position: parseInt(document.getElementById("l_position").value) || 0,
    }});
    document.getElementById("link-form").reset();
    alertBox.innerHTML = `<div class="success">لینک اضافه شد.</div>`;
    loadLinks();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

async function loadLinks() {{
  const container = document.getElementById("links-list");
  try {{
    const res = await fetch("/api/links");
    if (!res.ok) throw new Error("خطا در دریافت لینک‌ها");
    const data = await res.json();
    if (!data.items.length) {{
      container.innerHTML = '<p class="muted">هنوز لینکی اضافه نشده.</p>';
      return;
    }}
    container.innerHTML = data.items
      .map(
        (l) => `
      <div class="row list-item" data-id="${{l.id}}" style="justify-content:space-between;align-items:center;">
        <div><b>${{l.title}}</b> — <a href="${{l.url}}" target="_blank">${{l.url}}</a></div>
        <button type="button" class="danger small del-link-btn">حذف</button>
      </div>`
      )
      .join("");
    container.querySelectorAll(".del-link-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        if (!confirm("این لینک حذف بشه؟")) return;
        const id = btn.closest(".row").dataset.id;
        try {{
          await apiCall("/api/links/" + id, "DELETE");
          loadLinks();
        }} catch (err) {{
          alert(err.message);
        }}
      }});
    }});
  }} catch (err) {{
    container.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

async function loadTickets() {{
  const container = document.getElementById("tickets-list");
  try {{
    const data = await apiCall("/api/admin-data/tickets", "GET");
    if (!data.items.length) {{
      container.innerHTML = '<p class="muted">تیکتی ثبت نشده.</p>';
      return;
    }}
    container.innerHTML = data.items
      .map(
        (t) => `
      <div class="card" data-id="${{t.id}}" style="margin-bottom:10px;">
        <div class="row" style="justify-content:space-between;">
          <b>${{t.subject}}</b>
          <span class="status-badge">${{t.status}}</span>
        </div>
        <p class="muted" style="font-size:.85rem;">${{t.name}} — ${{t.phone}}</p>
        <p>${{t.message}}</p>
        <div class="row">
          <select class="status-select">
            <option ${{t.status === "در حال بررسی" ? "selected" : ""}}>در حال بررسی</option>
            <option ${{t.status === "پاسخ داده شد" ? "selected" : ""}}>پاسخ داده شد</option>
            <option ${{t.status === "بسته شد" ? "selected" : ""}}>بسته شد</option>
          </select>
          <button type="button" class="secondary small save-status-btn">بروزرسانی وضعیت</button>
          <button type="button" class="danger small del-ticket-btn">حذف</button>
        </div>
      </div>`
      )
      .join("");

    container.querySelectorAll(".save-status-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        const card = btn.closest(".card");
        const id = card.dataset.id;
        const status = card.querySelector(".status-select").value;
        try {{
          await apiCall("/api/admin-data/tickets/" + id, "PUT", {{ status }});
          loadTickets();
        }} catch (err) {{
          alert(err.message);
        }}
      }});
    }});
    container.querySelectorAll(".del-ticket-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        if (!confirm("این تیکت حذف بشه؟")) return;
        const id = btn.closest(".card").dataset.id;
        try {{
          await apiCall("/api/admin-data/tickets/" + id, "DELETE");
          loadTickets();
        }} catch (err) {{
          alert(err.message);
        }}
      }});
    }});
  }} catch (err) {{
    container.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

const CONTACT_FIELD_IDS = {{
  office_address: "ci_office_address",
  telegram_channel: "ci_telegram_channel",
  bale_channel: "ci_bale_channel",
  instagram_channel: "ci_instagram_channel",
  company_phone: "ci_company_phone",
}};

async function loadContactInfo() {{
  try {{
    const info = await apiCall("/api/admin-data/contact-info", "GET");
    Object.keys(CONTACT_FIELD_IDS).forEach((key) => {{
      document.getElementById(CONTACT_FIELD_IDS[key]).value = info[key] || "";
    }});
  }} catch (err) {{
    const box = document.getElementById("contact-alert-box");
    if (box) box.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

document.getElementById("contact-save-btn").addEventListener("click", async () => {{
  const box = document.getElementById("contact-alert-box");
  const payload = {{}};
  Object.keys(CONTACT_FIELD_IDS).forEach((key) => {{
    payload[key] = document.getElementById(CONTACT_FIELD_IDS[key]).value.trim();
  }});
  try {{
    const data = await apiCall("/api/admin-data/contact-info", "PUT", payload);
    box.innerHTML = `<div class="success">${{data.message}}</div>`;
  }} catch (err) {{
    box.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

document.querySelectorAll("[data-clear-field]").forEach((btn) => {{
  btn.addEventListener("click", async () => {{
    const field = btn.dataset.clearField;
    if (!confirm("این مقدار پاک بشه؟")) return;
    const box = document.getElementById("contact-alert-box");
    try {{
      const data = await apiCall("/api/admin-data/contact-info/" + field, "DELETE");
      document.getElementById(CONTACT_FIELD_IDS[field]).value = "";
      box.innerHTML = `<div class="success">${{data.message}}</div>`;
    }} catch (err) {{
      box.innerHTML = `<div class="error">${{err.message}}</div>`;
    }}
  }});
}});

async function loadUsers() {{
  const container = document.getElementById("users-list");
  try {{
    const data = await apiCall("/api/admin-data/users", "GET");
    if (!data.items.length) {{
      container.innerHTML = '<p class="muted">کاربری ثبت‌نام نکرده.</p>';
      return;
    }}
    const rows = data.items
      .map(
        (u) => `
      <tr>
        <td>${{u.full_name}}</td>
        <td>${{u.phone}}</td>
        <td>${{u.email || "-"}}</td>
        <td>${{u.field}}</td>
        <td>${{u.grade}}</td>
        <td>${{u.target_major || "-"}}</td>
      </tr>`
      )
      .join("");
    container.innerHTML = `
      <table>
        <thead><tr><th>نام</th><th>موبایل</th><th>ایمیل</th><th>رشته</th><th>پایه</th><th>رشته هدف</th></tr></thead>
        <tbody>${{rows}}</tbody>
      </table>`;
  }} catch (err) {{
    container.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

// ---------------------------------------------------------------------
// بانک سوالات آزمون
// ---------------------------------------------------------------------
let qbMetaLoaded = false;

async function initQuestionBankTab() {{
  if (!qbMetaLoaded) {{
    await loadQuestionBankMeta();
    qbMetaLoaded = true;
  }}
  loadQuestions();
}}

async function loadQuestionBankMeta() {{
  try {{
    const meta = await apiCall("/api/question-bank/meta", "GET");
    const gradeSelect = document.getElementById("qb_grade");
    const filterGradeSelect = document.getElementById("qb_filter_grade");
    const pdfGradeSelect = document.getElementById("qbp_grade");
    const imageGradeSelect = document.getElementById("qbi_grade");
    gradeSelect.innerHTML = meta.grades.map((g) => `<option value="${{g}}">${{g}}</option>`).join("");
    pdfGradeSelect.innerHTML = meta.grades.map((g) => `<option value="${{g}}">${{g}}</option>`).join("");
    imageGradeSelect.innerHTML = meta.grades.map((g) => `<option value="${{g}}">${{g}}</option>`).join("");
    filterGradeSelect.innerHTML =
      '<option value="">همه پایه‌ها</option>' +
      meta.grades.map((g) => `<option value="${{g}}">${{g}}</option>`).join("");

    const subjectList = document.getElementById("qb_subject_list");
    function refreshSubjects() {{
      const subs = meta.subjects_by_grade[gradeSelect.value] || [];
      subjectList.innerHTML = subs.map((s) => `<option value="${{s}}"></option>`).join("");
    }}
    gradeSelect.addEventListener("change", refreshSubjects);
    refreshSubjects();
  }} catch (err) {{
    document.getElementById("qb-alert-box").innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

document.getElementById("qb_type").addEventListener("change", (e) => {{
  const isEssay = e.target.value === "تشریحی";
  document.getElementById("qb-mcq-fields").style.display = isEssay ? "none" : "block";
  document.getElementById("qb-essay-fields").style.display = isEssay ? "block" : "none";
}});

document.getElementById("qb-form").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const alertBox = document.getElementById("qb-alert-box");
  const questionType = document.getElementById("qb_type").value;
  const payload = {{
    grade: document.getElementById("qb_grade").value,
    subject: document.getElementById("qb_subject").value,
    lesson: document.getElementById("qb_lesson").value,
    difficulty: document.getElementById("qb_difficulty").value,
    question_type: questionType,
    question_text: document.getElementById("qb_question_text").value,
  }};
  if (questionType === "تشریحی") {{
    payload.model_answer = document.getElementById("qb_model_answer").value;
  }} else {{
    payload.options = [
      document.getElementById("qb_opt0").value,
      document.getElementById("qb_opt1").value,
      document.getElementById("qb_opt2").value,
      document.getElementById("qb_opt3").value,
    ];
    payload.correct_index = parseInt(document.getElementById("qb_correct_index").value);
  }}

  try {{
    await apiCall("/api/question-bank", "POST", payload);
    alertBox.innerHTML = `<div class="success">سوال اضافه شد.</div>`;
    document.getElementById("qb-form").reset();
    loadQuestions();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

document.getElementById("qb-pdf-form").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const alertBox = document.getElementById("qb-pdf-alert-box");
  const fileInput = document.getElementById("qbp_file");
  if (!fileInput.files[0]) {{
    alertBox.innerHTML = `<div class="error">اول یک فایل PDF انتخاب کن.</div>`;
    return;
  }}
  const submitBtn = e.target.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "در حال استخراج سوالات با هوش مصنوعی... (ممکن است کمی طول بکشد)";
  alertBox.innerHTML = "";

  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  fd.append("grade", document.getElementById("qbp_grade").value);
  fd.append("subject", document.getElementById("qbp_subject").value);
  fd.append("lesson", document.getElementById("qbp_lesson").value);
  fd.append("difficulty", document.getElementById("qbp_difficulty").value);
  fd.append("question_type", document.getElementById("qbp_type").value);

  try {{
    const res = await fetch("/api/question-bank/upload-pdf", {{ method: "POST", body: fd }});
    if (!res.ok) {{
      const err = await res.json().catch(() => ({{ detail: "خطای ناشناخته" }}));
      throw new Error(err.detail || "خطا در پردازش PDF");
    }}
    const data = await res.json();
    alertBox.innerHTML = `<div class="success">${{data.message}}</div>`;
    document.getElementById("qb-pdf-form").reset();
    loadQuestions();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }} finally {{
    submitBtn.disabled = false;
    submitBtn.textContent = "استخراج و افزودن سوالات از PDF";
  }}
}});

document.getElementById("qb_filter_btn").addEventListener("click", loadQuestions);

document.getElementById("qb-image-form").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const alertBox = document.getElementById("qb-image-alert-box");
  const fileInput = document.getElementById("qbi_file");
  if (!fileInput.files[0]) {{
    alertBox.innerHTML = `<div class="error">اول یک فایل عکس یا PDF انتخاب کن.</div>`;
    return;
  }}
  const submitBtn = e.target.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "در حال خواندن عکس با هوش مصنوعی... (ممکن است کمی طول بکشد)";
  alertBox.innerHTML = "";

  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  fd.append("grade", document.getElementById("qbi_grade").value);
  fd.append("subject", document.getElementById("qbi_subject").value);
  fd.append("lesson", document.getElementById("qbi_lesson").value);
  fd.append("difficulty", document.getElementById("qbi_difficulty").value);

  try {{
    const res = await fetch("/api/question-bank/upload-image", {{ method: "POST", body: fd }});
    if (!res.ok) {{
      const err = await res.json().catch(() => ({{ detail: "خطای ناشناخته" }}));
      throw new Error(err.detail || "خطا در پردازش فایل");
    }}
    const data = await res.json();
    alertBox.innerHTML = `<div class="success">${{data.message}}</div>`;
    document.getElementById("qb-image-form").reset();
    loadQuestions();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }} finally {{
    submitBtn.disabled = false;
    submitBtn.textContent = "استخراج سوال و پاسخ از عکس/PDF";
  }}
}});

async function loadQuestions() {{
  const container = document.getElementById("qb-list");
  const grade = document.getElementById("qb_filter_grade").value;
  const subject = document.getElementById("qb_filter_subject").value;
  const params = new URLSearchParams();
  if (grade) params.set("grade", grade);
  if (subject) params.set("subject", subject);
  try {{
    const data = await apiCall("/api/question-bank?" + params.toString(), "GET");
    if (!data.items.length) {{
      container.innerHTML = '<p class="muted">سوالی با این فیلتر پیدا نشد.</p>';
      return;
    }}
    container.innerHTML = data.items
      .map(
        (q) => `
      <div class="card" data-id="${{q.id}}" style="margin-bottom:10px;">
        <div class="row" style="justify-content:space-between;">
          <span class="status-badge">${{q.grade}} — ${{q.subject}}${{q.lesson ? " — " + q.lesson : ""}}</span>
          <span class="status-badge">${{q.difficulty}} / ${{q.question_type}}</span>
          ${{q.source === "ai_extracted" ? '<span class="status-badge">🖼️ استخراج از عکس/PDF</span>' : ""}}
        </div>
        <p style="margin-top:8px;">${{q.question_text}}</p>
        ${{
          q.question_type === "تستی"
            ? `<ul style="font-size:.82rem;color:#50575e;">${{q.options
                .map((o, i) => `<li>${{i === q.correct_index ? "✅ " : ""}}${{o}}</li>`)
                .join("")}}</ul>`
            : `<p style="font-size:.82rem;color:#50575e;">پاسخ نمونه: ${{q.model_answer || "-"}}</p>`
        }}
        <button type="button" class="danger small del-question-btn">حذف</button>
      </div>`
      )
      .join("");
    container.querySelectorAll(".del-question-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        if (!confirm("این سوال حذف بشه؟")) return;
        const id = btn.closest(".card").dataset.id;
        try {{
          await apiCall("/api/question-bank/" + id, "DELETE");
          loadQuestions();
        }} catch (err) {{
          alert(err.message);
        }}
      }});
    }});
  }} catch (err) {{
    container.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

// ---------------------------------------------------------------------
// مشاوره‌های دانش‌آموزان
// ---------------------------------------------------------------------
async function loadConsultationsList() {{
  document.getElementById("consult-list-card").style.display = "block";
  document.getElementById("consult-transcript-card").style.display = "none";
  const container = document.getElementById("consult-admin-list");
  try {{
    const data = await apiCall("/api/admin-data/consultations", "GET");
    if (!data.items.length) {{
      container.innerHTML = '<p class="muted">هنوز دانش‌آموزی با مشاوره هوشمند گفت‌وگو نکرده.</p>';
      return;
    }}
    container.innerHTML = data.items
      .map(
        (c) => `
      <div class="list-item" data-user-id="${{c.user_id}}" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;">
        <div><b>${{c.full_name}}</b><br/><span class="muted" style="font-size:.78rem;">${{c.last_message}}</span></div>
        <span class="status-badge">${{c.message_count}} پیام</span>
      </div>`
      )
      .join("");
    container.querySelectorAll(".list-item").forEach((row) => {{
      row.addEventListener("click", () => openConsultTranscript(row.dataset.userId));
    }});
  }} catch (err) {{
    container.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

async function openConsultTranscript(userId) {{
  document.getElementById("consult-list-card").style.display = "none";
  document.getElementById("consult-transcript-card").style.display = "block";
  const container = document.getElementById("consult-transcript");
  container.innerHTML = "در حال بارگذاری...";
  try {{
    const data = await apiCall("/api/admin-data/consultations/" + userId, "GET");
    container.innerHTML = data.items
      .map(
        (m) => `
      <div class="list-item">
        <b>${{m.role === "user" ? "دانش‌آموز" : "مشاوره هوشمند"}}:</b>
        <span style="white-space:pre-wrap;">${{m.content}}</span>
      </div>`
      )
      .join("");
  }} catch (err) {{
    container.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

document.getElementById("consult-back-btn").addEventListener("click", loadConsultationsList);

// ---------------------------------------------------------------------
// انتخاب رشته — مدیریت کدرشته‌ها
// ---------------------------------------------------------------------
document.getElementById("mc-form").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const alertBox = document.getElementById("mc-alert-box");
  const payload = {{
    code: document.getElementById("mc_code").value,
    university_name: document.getElementById("mc_university").value,
    major_name: document.getElementById("mc_major").value,
    city: document.getElementById("mc_city").value,
    ownership_type: document.getElementById("mc_ownership").value,
    field_group: document.getElementById("mc_field_group").value,
    min_rank: document.getElementById("mc_min_rank").value ? parseInt(document.getElementById("mc_min_rank").value) : null,
    max_rank: document.getElementById("mc_max_rank").value ? parseInt(document.getElementById("mc_max_rank").value) : null,
    notes: document.getElementById("mc_notes").value,
  }};
  try {{
    await apiCall("/api/major-codes", "POST", payload);
    alertBox.innerHTML = `<div class="success">کدرشته اضافه شد.</div>`;
    document.getElementById("mc-form").reset();
    loadMajorCodes();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

document.getElementById("mc-csv-upload-btn").addEventListener("click", async () => {{
  const fileInput = document.getElementById("mc_csv_file");
  const alertBox = document.getElementById("mc-csv-alert-box");
  if (!fileInput.files[0]) {{
    alertBox.innerHTML = `<div class="error">اول یک فایل CSV انتخاب کن.</div>`;
    return;
  }}
  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  try {{
    const res = await fetch("/api/major-codes/upload-csv", {{ method: "POST", body: fd }});
    if (!res.ok) {{
      const err = await res.json().catch(() => ({{ detail: "خطای ناشناخته" }}));
      throw new Error(err.detail || "خطا در آپلود CSV");
    }}
    const data = await res.json();
    alertBox.innerHTML = `<div class="success">${{data.message}}</div>`;
    fileInput.value = "";
    loadMajorCodes();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

document.getElementById("mc-pdf-upload-btn").addEventListener("click", async () => {{
  const fileInput = document.getElementById("mc_pdf_file");
  const alertBox = document.getElementById("mc-pdf-alert-box");
  if (!fileInput.files[0]) {{
    alertBox.innerHTML = `<div class="error">اول یک فایل PDF انتخاب کن.</div>`;
    return;
  }}
  const btn = document.getElementById("mc-pdf-upload-btn");
  btn.disabled = true;
  btn.textContent = "در حال استخراج با هوش مصنوعی... (ممکن است کمی طول بکشد)";
  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  try {{
    const res = await fetch("/api/major-codes/upload-pdf", {{ method: "POST", body: fd }});
    if (!res.ok) {{
      const err = await res.json().catch(() => ({{ detail: "خطای ناشناخته" }}));
      throw new Error(err.detail || "خطا در آپلود PDF");
    }}
    const data = await res.json();
    alertBox.innerHTML = `<div class="success">${{data.message}}</div>`;
    fileInput.value = "";
    loadMajorCodes();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }} finally {{
    btn.disabled = false;
    btn.textContent = "استخراج و افزودن از PDF";
  }}
}});

document.getElementById("mc-search-btn").addEventListener("click", () => loadMajorCodes());

async function loadMajorCodes() {{
  const container = document.getElementById("mc-list");
  const search = document.getElementById("mc_search").value || "";
  try {{
    const data = await apiCall("/api/major-codes?search=" + encodeURIComponent(search), "GET");
    document.getElementById("mc-total-count").textContent = `مجموع کدرشته‌های ثبت‌شده: ${{data.total_count}}`;
    if (!data.items.length) {{
      container.innerHTML = '<p class="muted">کدرشته‌ای پیدا نشد.</p>';
      return;
    }}
    container.innerHTML = data.items
      .map(
        (c) => `
      <div class="list-item" data-id="${{c.id}}" style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <b>${{c.university_name}}</b> — ${{c.major_name}}<br/>
          <span class="muted" style="font-size:.78rem;">${{c.city || "-"}} | ${{c.ownership_type || "-"}} | کد: ${{c.code || "-"}} | رتبه: ${{c.min_rank || "-"}}-${{c.max_rank || "-"}}</span>
        </div>
        <button type="button" class="danger small del-mc-btn">حذف</button>
      </div>`
      )
      .join("");
    container.querySelectorAll(".del-mc-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        if (!confirm("این کدرشته حذف بشه؟")) return;
        const id = btn.closest(".list-item").dataset.id;
        try {{
          await apiCall("/api/major-codes/" + id, "DELETE");
          loadMajorCodes();
        }} catch (err) {{
          alert(err.message);
        }}
      }});
    }});
  }} catch (err) {{
    container.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}

// ---------------------------------------------------------------------
// قیمت‌گذاری
// ---------------------------------------------------------------------
document.getElementById("pr-form").addEventListener("submit", async (e) => {{
  e.preventDefault();
  const alertBox = document.getElementById("pr-alert-box");
  const payload = {{
    plan_key: document.getElementById("pr_plan_key").value.trim(),
    title: document.getElementById("pr_title").value.trim(),
    description: document.getElementById("pr_description").value,
    price: parseInt(document.getElementById("pr_price").value) || 0,
    price_label: document.getElementById("pr_price_label").value.trim(),
    duration: document.getElementById("pr_duration").value,
    position: parseInt(document.getElementById("pr_position").value) || 0,
  }};
  try {{
    await apiCall("/api/subscription/admin/plans", "POST", payload);
    alertBox.innerHTML = `<div class="success">پلن اضافه شد.</div>`;
    document.getElementById("pr-form").reset();
    loadPricingPlans();
  }} catch (err) {{
    alertBox.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}});

async function loadPricingPlans() {{
  const container = document.getElementById("pr-list");
  try {{
    const data = await apiCall("/api/subscription/admin/plans", "GET");
    if (!data.items.length) {{
      container.innerHTML = '<p class="muted">هنوز پلنی ثبت نشده.</p>';
      return;
    }}
    container.innerHTML = data.items
      .map(
        (p) => `
      <div class="card plan-row" data-id="${{p.id}}" style="margin-bottom:10px;">
        <div class="row" style="justify-content:space-between;">
          <b>${{p.title}}</b>
          <span class="status-badge">${{p.price_label}}</span>
        </div>
        <p class="muted" style="font-size:.82rem;">شناسه: ${{p.plan_key}} | مدت: ${{p.duration || "-"}} | اولویت: ${{p.position}}</p>
        <p>${{p.description || ""}}</p>
        <div class="row">
          <button type="button" class="secondary small edit-plan-btn">ویرایش</button>
          <button type="button" class="danger small del-plan-btn">حذف</button>
        </div>
      </div>`
      )
      .join("");

    container.querySelectorAll(".del-plan-btn").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        if (!confirm("این پلن حذف بشه؟")) return;
        const id = btn.closest(".plan-row").dataset.id;
        try {{
          await apiCall("/api/subscription/admin/plans/" + id, "DELETE");
          loadPricingPlans();
        }} catch (err) {{
          alert(err.message);
        }}
      }});
    }});

    container.querySelectorAll(".edit-plan-btn").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        const row = btn.closest(".plan-row");
        const p = data.items.find((x) => x.id === parseInt(row.dataset.id));
        row.innerHTML = `
          <label>شناسه پلن</label>
          <input type="text" class="e-plan-key" value="${{p.plan_key}}" />
          <label>عنوان</label>
          <input type="text" class="e-title" value="${{p.title}}" />
          <label>توضیحات</label>
          <input type="text" class="e-desc" value="${{p.description || ""}}" />
          <label>قیمت (عدد)</label>
          <input type="number" class="e-price" value="${{p.price}}" />
          <label>برچسب قیمت</label>
          <input type="text" class="e-price-label" value="${{p.price_label}}" />
          <label>مدت</label>
          <input type="text" class="e-duration" value="${{p.duration || ""}}" />
          <label>اولویت</label>
          <input type="number" class="e-position" value="${{p.position}}" />
          <div class="row">
            <button type="button" class="save-plan-btn">ذخیره</button>
            <button type="button" class="secondary cancel-plan-btn">انصراف</button>
          </div>
        `;
        row.querySelector(".cancel-plan-btn").addEventListener("click", loadPricingPlans);
        row.querySelector(".save-plan-btn").addEventListener("click", async () => {{
          try {{
            await apiCall("/api/subscription/admin/plans/" + p.id, "PUT", {{
              plan_key: row.querySelector(".e-plan-key").value.trim(),
              title: row.querySelector(".e-title").value.trim(),
              description: row.querySelector(".e-desc").value,
              price: parseInt(row.querySelector(".e-price").value) || 0,
              price_label: row.querySelector(".e-price-label").value.trim(),
              duration: row.querySelector(".e-duration").value,
              position: parseInt(row.querySelector(".e-position").value) || 0,
            }});
            loadPricingPlans();
          }} catch (err) {{
            alert(err.message);
          }}
        }});
      }});
    }});
  }} catch (err) {{
    container.innerHTML = `<div class="error">${{err.message}}</div>`;
  }}
}}
</script>
</body></html>"""
