"""
تولید صفحات HTML به صورت رشته‌های پایتون؛ جایگزین فولدر templates.
"""
from assets import CSS_TEXT, THEME_JS, MAIN_JS, PLAN_JS, EXAM_JS, CONSULT_JS, MAJOR_JS, LOGO_DATA_URI, BG3D_JS
from support_router import SUPPORT_FAQ
import curriculum
import models
import json
import os

# آدرس اصلی دامنه سایت روی Render (برای canonical و og:url). بعد از دیپلوی از طریق
# متغیر محیطی SITE_URL روی Render مقداردهی کن، مثلاً: https://noortika.onrender.com
# اگر این متغیر محیطی ست نشده باشد، به آدرس پیش‌فرض Render برمی‌گردیم تا
# canonical/og:url/robots.txt هیچ‌وقت نسبی (invalid) نشوند — چون یک URL نسبی
# در تگ <link rel="canonical"> یا خط Sitemap در robots.txt توسط ابزارهایی مثل
# PageSpeed/Lighthouse نامعتبر (Invalid) گزارش می‌شود.
SITE_URL = (os.environ.get("SITE_URL", "") or "https://noortika.onrender.com").rstrip("/")


def _ld_json(data) -> str:
    """یک بلوک اسکریپت JSON-LD امن (با escape درست) برمی‌گرداند."""
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False)
        + "</script>"
    )


def _organization_website_schema(active_path: str) -> str:
    """اسکیمای Organization + WebSite که در همه صفحات سایت تکرار می‌شود."""
    graph = [
        {
            "@type": ["EducationalOrganization", "Organization"],
            "@id": f"{SITE_URL}/#organization",
            "name": "نورتیکا",
            "alternateName": "Noortika",
            "url": SITE_URL or "/",
            "logo": {
                "@type": "ImageObject",
                "url": f"{SITE_URL}/logo.jpg",
            },
            "description": "سایت تخصصی نورتیکا؛ برنامه‌ریزی درسی هوشمند، آزمون آنلاین و مشاوره تحصیلی با هوش مصنوعی برای دانش‌آموزان متوسطه اول و دوم.",
        },
        {
            "@type": "WebSite",
            "@id": f"{SITE_URL}/#website",
            "name": "نورتیکا",
            "url": SITE_URL or "/",
            "inLanguage": "fa-IR",
            "publisher": {"@id": f"{SITE_URL}/#organization"},
        },
    ]
    return _ld_json({"@context": "https://schema.org", "@graph": graph})


def _build_course_items():
    """فهرست یکتای دروس/کتاب‌های متوسطه اول و دوم (از curriculum.py) برای Course schema
    و برای نمایش بصری «پوشش کامل کتاب‌های درسی» در صفحه برنامه‌ریزی."""
    seen = set()
    grades_map = {}
    for grade, fields in curriculum.CURRICULUM.items():
        grade_subjects = grades_map.setdefault(grade, {})
        for field, subjects in fields.items():
            for subj in subjects:
                key = (grade, subj["name"])
                if key in seen:
                    continue
                seen.add(key)
                grade_subjects[subj["name"]] = subj["topics"]
    return grades_map


COURSE_CATALOG = _build_course_items()


def _course_schema() -> str:
    items = []
    position = 1
    for grade, subjects in COURSE_CATALOG.items():
        for name, topics in subjects.items():
            items.append({
                "@type": "ListItem",
                "position": position,
                "item": {
                    "@type": "Course",
                    "name": f"{name} - پایه {grade}",
                    "description": "سرفصل‌های این کتاب: " + "، ".join(topics) + ".",
                    "educationalLevel": grade,
                    "provider": {
                        "@type": "Organization",
                        "name": "نورتیکا",
                        "sameAs": SITE_URL or None,
                    },
                    "inLanguage": "fa-IR",
                },
            })
            position += 1
    data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "کتاب‌های درسی پوشش داده‌شده در برنامه‌ریزی نورتیکا",
        "numberOfItems": len(items),
        "itemListElement": items,
    }
    return _ld_json(data)


def _course_catalog_html() -> str:
    """نمایش بصری خلاصه از کتاب‌های هر پایه، برای هم‌خوانی محتوای صفحه با Course schema."""
    grade_order = ["هفتم", "هشتم", "نهم", "دهم", "یازدهم", "دوازدهم"]
    blocks = []
    for grade in grade_order:
        subjects = COURSE_CATALOG.get(grade, {})
        if not subjects:
            continue
        names = "، ".join(subjects.keys())
        blocks.append(f"""
    <details class="day-card">
      <summary><b>پایه {grade}</b> ({len(subjects)} کتاب)</summary>
      <p style="margin:10px 0 0;color:var(--text-muted);font-size:0.9rem;">{names}</p>
    </details>""")
    return "\n".join(blocks)


def _faq_schema(faq_items) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in faq_items
        ],
    }
    return _ld_json(data)


def _faq_list_html(faq_items) -> str:
    return "\n".join(
        f'<div class="day-card"><b>{item["q"]}</b>'
        f'<p style="margin:8px 0 0;color:var(--text-muted);">{item["a"]}</p></div>'
        for item in faq_items
    )


# ۵ سؤال متداول اختصاصی صفحه اصلی (درباره ثبت‌نام و شروع کار با نورتیکا)؛
# جدا از SUPPORT_FAQ نگه داشته شده چون موضوعش با صفحه پشتیبانی فرق دارد.
HOME_FAQ = [
    {"q": "نورتیکا برای چه پایه‌هایی مناسب است؟",
     "a": "نورتیکا تمام دانش‌آموزان متوسطه اول (هفتم، هشتم، نهم) و متوسطه دوم (دهم، یازدهم، دوازدهم) در رشته‌های ریاضی فیزیک، علوم تجربی، علوم انسانی و فنی‌حرفه‌ای را پوشش می‌دهد."},
    {"q": "برنامه درسی چطور با هوش مصنوعی ساخته می‌شود؟",
     "a": "بعد از ثبت‌نام و مشخص‌کردن پایه، رشته و رشته هدف دانشگاهی، کافی است در صفحه برنامه با هوش مصنوعی نورتیکا مثل یک چت صحبت کنی تا یک برنامه مطالعاتی اختصاصی روزانه برایت طراحی شود."},
    {"q": "آیا همه کتاب‌های درسی و فصل‌ها پوشش داده می‌شود؟",
     "a": "بله، نورتیکا تمام کتاب‌های درسی متوسطه اول و دوم را به‌طور کامل و فصل‌به‌فصل در برنامه‌ریزی و طراحی آزمون در نظر می‌گیرد."},
    {"q": "آزمون‌های نورتیکا چه نوعی هستند؟",
     "a": "آزمون‌ها به دو صورت تستی (چهارگزینه‌ای) و تشریحی (تایپی) در سه سطح آسان، متوسط و سخت طراحی می‌شوند و پاسخ‌های غلط با تحلیل هوش مصنوعی بررسی می‌شوند."},
    {"q": "ثبت‌نام در نورتیکا هزینه دارد؟",
     "a": "ثبت‌نام اولیه و استفاده پایه رایگان است؛ برای امکانات کامل‌تر می‌توانی از صفحه اشتراک یکی از پلن‌ها را انتخاب کنی."},
]

NAV_ITEMS = [
    ("/", "ثبت‌نام"),
    ("/plan", "برنامه درسی"),
    ("/exam", "آزمون"),
    ("/consultation", "مشاوره تحصیلی"),
    ("/major-selection", "انتخاب رشته"),
    ("/blog", "وبلاگ"),
    ("/leaderboard", "رتبه‌بندی"),
    ("/pricing", "اشتراک"),
    ("/support", "پشتیبانی"),
]

# این صفحات فقط برای کاربرهای ثبت‌نام‌کرده/واردشده فعال هستند؛ برای مهمان‌ها در
# منو غیرفعال (خاکستری) نمایش داده می‌شوند و با کلیک به صفحه ورود هدایت می‌شوند.
GATED_PATHS = {"/plan", "/exam", "/consultation", "/major-selection"}


def _nav_html(active_path):
    links = []
    for href, label in NAV_ITEMS:
        cls = "active" if href == active_path else ""
        gated_attr = ' data-gated="1"' if href in GATED_PATHS else ""
        links.append(f'<a href="{href}" class="{cls}"{gated_attr}>{label}</a>')
    return "\n".join(links)


def _breadcrumb_label(active_path: str) -> str:
    for href, label in NAV_ITEMS:
        if href == active_path:
            return label
    return ""


def _breadcrumb_items_for(active_path: str):
    """مسیر پیش‌فرض breadcrumb برای صفحات تک‌سطحی؛ صفحه اصلی مسیر ندارد."""
    if active_path == "/":
        return None
    label = _breadcrumb_label(active_path)
    if not label:
        return None
    return [("خانه", "/"), (label, active_path)]


def _breadcrumb_schema(items) -> str:
    """اسکیمای BreadcrumbList از یک لیست [(نام, مسیر), ...]."""
    if not items:
        return ""
    list_items = [
        {"@type": "ListItem", "position": i, "name": name, "item": f"{SITE_URL}{href}"}
        for i, (name, href) in enumerate(items, start=1)
    ]
    data = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": list_items}
    return _ld_json(data)


def _breadcrumb_html(items) -> str:
    """نسخه دیدنیِ مسیر صفحه؛ باید دقیقاً با BreadcrumbList schema هم‌خوان باشد."""
    if not items:
        return ""
    parts = []
    last = len(items) - 1
    for i, (name, href) in enumerate(items):
        if i == last:
            parts.append(f'<span aria-current="page">{name}</span>')
        else:
            parts.append(f'<a href="{href}" style="color:var(--text-muted);text-decoration:none;">{name}</a>')
    inner = '<span style="margin:0 6px;">/</span>'.join(parts)
    return f"""
  <nav class="breadcrumb-nav" aria-label="breadcrumb" style="max-width:1100px;margin:14px auto 0;padding:0 16px;font-size:0.85rem;color:var(--text-muted);">
    {inner}
  </nav>"""


def base_page(title: str, active_path: str, body_html: str, extra_script: str = "",
              meta_description: str = "سایت تخصصی نورتیکا", extra_schema: str = "",
              breadcrumb_items=None, og_image: str = "") -> str:
    if breadcrumb_items is None:
        breadcrumb_items = _breadcrumb_items_for(active_path)
    image_url = og_image or f"{SITE_URL}/logo.jpg"
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{meta_description}" />
  <meta name="robots" content="index, follow" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="نورتیکا" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{meta_description}" />
  <meta property="og:url" content="{SITE_URL}{active_path}" />
  <meta property="og:image" content="{image_url}" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{meta_description}" />
  <meta name="twitter:image" content="{image_url}" />
  <link rel="canonical" href="{SITE_URL}{active_path}" />
  <title>{title}</title>
  <link rel="preload" href="/logo.jpg" as="image" type="image/webp" fetchpriority="high" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap" onload="this.onload=null;this.rel='stylesheet'">
  <noscript><link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap" rel="stylesheet"></noscript>
  <link rel="icon" type="image/webp" href="/logo.jpg" />
  {_organization_website_schema(active_path)}
  {_breadcrumb_schema(breadcrumb_items)}
  {extra_schema}
  <style>{CSS_TEXT}</style>
  <script>{THEME_JS}</script>
</head>
<body>
  <canvas id="bg3d-canvas"></canvas>

  <nav class="navbar">
    <div class="brand"><img src="/logo.jpg" alt="لوگوی نورتیکا" class="brand-logo" loading="eager" fetchpriority="high" width="40" height="40" /> نورتیکا</div>
    <div class="navbar-actions">
      <button id="theme-toggle-btn" class="theme-toggle">🌙 حالت شب</button>
      <button id="nav-hamburger-btn" class="nav-hamburger" aria-label="باز کردن منو" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
    </div>
    <div class="nav-links" id="nav-links-menu">
      {_nav_html(active_path)}
    </div>
  </nav>
  <div id="nav-overlay" class="nav-overlay"></div>
  {_breadcrumb_html(breadcrumb_items)}

  <main class="container">
    {body_html}
  </main>

  <footer>
    <img src="/logo.jpg" alt="لوگوی نورتیکا" class="footer-logo" loading="lazy" width="34" height="34" />
    نورتیکا، نوری در مسیر تاریکی تو! · © تمامی حقوق محفوظ است.
  </footer>

  <script>
{MAIN_JS}
  </script>
  <script>
  // پس‌زمینه سه‌بعدی صرفاً تزئینی است؛ برای اینکه رشته‌ی رندر اصلی و
  // First Contentful Paint / LCP را بلاک نکند، three.js و اسکریپت آن را
  // فقط بعد از بارگذاری کامل صفحه (و در زمان بیکاری مرورگر) لود می‌کنیم.
  (function () {{
    function loadBg3D() {{
      var s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
      s.onload = function () {{
        var s2 = document.createElement('script');
        s2.src = '/static/bg3d.js';
        document.body.appendChild(s2);
      }};
      document.body.appendChild(s);
    }}
    if ('requestIdleCallback' in window) {{
      window.addEventListener('load', function () {{ requestIdleCallback(loadBg3D, {{ timeout: 2000 }}); }});
    }} else {{
      window.addEventListener('load', function () {{ setTimeout(loadBg3D, 300); }});
    }}
  }})();
  </script>
  <script>
{extra_script}
  </script>
</body>
</html>"""


def not_found_page() -> str:
    body = """
  <div class="card" style="max-width:560px;margin:60px auto;text-align:center;">
    <h1>صفحه پیدا نشد (۴۰۴)</h1>
    <p style="color:var(--text-muted);">آدرسی که دنبالش بودی وجود نداره یا جابه‌جا شده.</p>
    <a href="/" class="btn" style="margin-top:16px;display:inline-block;">بازگشت به صفحه اصلی نورتیکا</a>
  </div>"""
    return base_page(
        title="صفحه پیدا نشد | نورتیکا",
        active_path="/404",
        body_html=body,
        meta_description="این صفحه در نورتیکا پیدا نشد.",
        breadcrumb_items=[("نورتیکا", "/"), ("صفحه پیدا نشد", "/404")],
    ).replace('<meta name="robots" content="index, follow" />', '<meta name="robots" content="noindex, follow" />')


def server_error_page() -> str:
    body = """
  <div class="card" style="max-width:560px;margin:60px auto;text-align:center;">
    <h1>خطای سرور (۵۰۰)</h1>
    <p style="color:var(--text-muted);">یک مشکل موقت پیش اومده. لطفاً چند لحظه دیگه دوباره امتحان کن.</p>
    <a href="/" class="btn" style="margin-top:16px;display:inline-block;">بازگشت به صفحه اصلی نورتیکا</a>
  </div>"""
    return base_page(
        title="خطای سرور | نورتیکا",
        active_path="/500",
        body_html=body,
        meta_description="خطای موقت سرور نورتیکا.",
        breadcrumb_items=[("نورتیکا", "/"), ("خطای سرور", "/500")],
    ).replace('<meta name="robots" content="index, follow" />', '<meta name="robots" content="noindex, follow" />')


def index_page(db=None) -> str:
    _latest = _db_posts(db)[:4]
    if _latest:
        _latest_cards = "".join(
            f"""
<a href="/blog/{p.slug}" class="card" style="display:block;text-decoration:none;color:inherit;">
  {f'<img src="{p.image_url}" alt="{p.title}" loading="lazy" style="width:100%;aspect-ratio:16/9;border-radius:12px;margin-bottom:12px;object-fit:cover;max-height:180px;" />' if getattr(p, "image_url", None) else ""}
  <span class="badge-note">مقاله جدید</span>
  <h3 style="margin-top:10px;">{p.title}</h3>
  <p style="color:var(--text-muted);">{p.description[:120]}{"..." if len(p.description) > 120 else ""}</p>
</a>"""
            for p in _latest
        )
        latest_posts_html = f"""
<div class="card">
  <h2>آخرین مقالات وبلاگ</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;">
    {_latest_cards}
  </div>
  <p style="margin-top:16px;"><a href="/blog">مشاهده همه مقالات وبلاگ →</a></p>
</div>
"""
    else:
        latest_posts_html = ""

    body = """
<div class="hero">
  <img src="/logo.jpg" alt="لوگوی نورتیکا" class="brand-logo-watermark" width="120" height="120" fetchpriority="high" loading="eager" />
  <h1>نورتیکا، نوری در مسیر تاریکی تو!</h1>
  <p>سایت تخصصی نورتیکا برنامه‌ریزی تحصیلی برای دانش‌آموزان متوسطه اول (هفتم، هشتم، نهم) و متوسطه دوم (دهم تا دوازدهم و فنی‌حرفه‌ای)؛ برنامه درسی اختصاصی با چت هوشمند، آزمون تستی و تشریحی، و رتبه‌بندی با جایزه.</p>
</div>

<div class="card" id="login-card" style="max-width:520px;">
  <h2>ورود به حساب کاربری</h2>
  <div id="alert-box"></div>
  <form id="login-form">
    <div class="form-grid" style="grid-template-columns:1fr;">
      <div class="field">
        <label>شماره تلفن</label>
        <input type="tel" id="login_phone" required placeholder="09xxxxxxxxx" />
      </div>
      <div class="field">
        <label>رمز عبور</label>
        <input type="password" id="login_password" required placeholder="رمز عبور خود را وارد کنید" />
      </div>
    </div>
    <div style="margin-top:20px;">
      <button type="submit" class="btn block">ورود به داشبورد</button>
    </div>
  </form>
  <p style="margin-top:16px;text-align:center;color:var(--text-muted);">
    حساب کاربری نداری؟
    <a href="#" id="show-register-link" style="color:var(--primary);font-weight:700;">همین‌جا ثبت‌نام کن</a>
  </p>
  <p style="margin-top:6px;text-align:center;">
    <a href="#" id="show-forgot-link" style="color:var(--text-muted);font-size:0.88rem;">رمز عبور را فراموش کرده‌اید؟</a>
  </p>
</div>

<div class="card" id="register-card" style="max-width:680px;display:none;">
  <h2>ثبت‌نام و شروع مسیر</h2>
  <div id="register-alert-box"></div>
  <form id="register-form">
    <div class="form-grid">
      <div class="field">
        <label>نام و نام خانوادگی</label>
        <input type="text" id="full_name" required />
      </div>
      <div class="field">
        <label>شماره تلفن</label>
        <input type="tel" id="phone" required placeholder="09xxxxxxxxx" />
      </div>
      <div class="field">
        <label>ایمیل</label>
        <input type="email" id="email" required placeholder="you@example.com" />
      </div>
      <div class="field">
        <label>رمز عبور</label>
        <input type="password" id="password" required minlength="4" placeholder="یک رمز عبور انتخاب کن" />
      </div>
      <div class="field">
        <label>پایه تحصیلی</label>
        <select id="grade" required>
          <option value="">انتخاب کنید</option>
          <option value="هفتم">هفتم (متوسطه اول)</option>
          <option value="هشتم">هشتم (متوسطه اول)</option>
          <option value="نهم">نهم (متوسطه اول)</option>
          <option value="دهم">دهم</option>
          <option value="یازدهم">یازدهم</option>
          <option value="دوازدهم">دوازدهم</option>
        </select>
      </div>
      <div class="field">
        <label>گروه تحصیلی (رشته)</label>
        <select id="field" required>
          <option value="">انتخاب کنید</option>
          <option value="عمومی">عمومی (متوسطه اول)</option>
          <option value="ریاضی فیزیک">ریاضی فیزیک</option>
          <option value="علوم تجربی">علوم تجربی</option>
          <option value="علوم انسانی">علوم انسانی</option>
          <option value="فنی حرفه‌ای">فنی حرفه‌ای</option>
        </select>
      </div>
      <div class="field">
        <label>رشته هدف دانشگاهی</label>
        <input type="text" id="target_major" placeholder="مثلاً پزشکی، مهندسی کامپیوتر" />
      </div>
      <div class="field">
        <label>دانشگاه هدف</label>
        <input type="text" id="target_university" placeholder="مثلاً دانشگاه تهران" />
      </div>
      <div class="field" style="grid-column: 1 / -1;">
        <label>ساعت مطالعه در روز (تقریبی)</label>
        <input type="number" id="daily_hours" min="0.5" max="16" step="0.5" value="3" required />
      </div>
    </div>
    <div style="margin-top:20px;">
      <button type="submit" class="btn block">ثبت‌نام</button>
    </div>
  </form>
  <p style="margin-top:16px;text-align:center;color:var(--text-muted);">
    قبلاً ثبت‌نام کردی؟
    <a href="#" id="show-login-link" style="color:var(--primary);font-weight:700;">وارد شو</a>
  </p>
</div>

<div class="card" id="forgot-card" style="max-width:520px;display:none;">
  <h2>فراموشی رمز عبور</h2>
  <p style="color:var(--text-muted);font-size:0.9rem;">ایمیلی که موقع ثبت‌نام وارد کردی رو بزن؛ یک کد ۶ رقمی به همون ایمیل می‌فرستیم.</p>
  <div id="forgot-alert-box"></div>
  <form id="forgot-form">
    <div class="field">
      <label>ایمیل</label>
      <input type="email" id="forgot_email" required placeholder="you@example.com" />
    </div>
    <div style="margin-top:16px;">
      <button type="submit" class="btn block">ارسال کد</button>
    </div>
  </form>
  <p style="margin-top:16px;text-align:center;">
    <a href="#" id="back-to-login-from-forgot" style="color:var(--text-muted);font-size:0.88rem;">بازگشت به ورود</a>
  </p>
</div>

<div class="card" id="code-card" style="max-width:520px;display:none;">
  <h2>وارد کردن کد تایید</h2>
  <p style="color:var(--text-muted);font-size:0.9rem;">کدی که به ایمیل ثبت‌نامی‌ات ارسال شد رو وارد کن.</p>
  <p style="margin-top:4px;"><strong>زمان باقی‌مانده: <span id="code-timer">۰۲:۰۰</span></strong></p>
  <div id="code-alert-box"></div>
  <form id="code-form">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
      <img src="/icons/gmail.png" alt="جی‌میل" style="width:26px;height:26px;object-fit:cover;" />
      <span style="font-size:0.88rem;color:var(--text-muted);">کد به جی‌میل شما ارسال شد</span>
    </div>
    <div class="field">
      <label>کد ۶ رقمی</label>
      <input type="text" id="reset_code" required maxlength="6" inputmode="numeric" placeholder="۱۲۳۴۵۶" />
    </div>
    <div style="margin-top:16px;">
      <button type="submit" class="btn block" id="code-submit-btn">تایید کد</button>
    </div>
  </form>
  <p style="margin-top:16px;text-align:center;">
    <a href="#" id="resend-code-link" style="color:var(--text-muted);font-size:0.88rem;">کد جدید بفرست</a>
  </p>
</div>

<div class="card" id="reset-card" style="max-width:520px;display:none;">
  <h2>تغییر رمز عبور</h2>
  <p style="color:var(--text-muted);font-size:0.9rem;">رمز عبور جدیدت رو انتخاب کن.</p>
  <div id="reset-alert-box"></div>
  <form id="reset-form">
    <div class="field">
      <label>رمز عبور جدید</label>
      <input type="password" id="reset_new_password" required minlength="4" placeholder="رمز جدید" />
    </div>
    <div style="margin-top:16px;">
      <button type="submit" class="btn block">تغییر رمز عبور</button>
    </div>
  </form>
  <p style="margin-top:16px;text-align:center;">
    <a href="#" id="back-to-forgot-from-reset" style="color:var(--text-muted);font-size:0.88rem;">بازگشت</a>
  </p>
</div>

<div class="card">
  <h2>چرا برنامه‌ریزی تحصیلی هوشمند اهمیت دارد؟</h2>
  <p>خیلی از دانش‌آموزان متوسطه اول و متوسطه دوم ساعت‌های زیادی درس می‌خوانند اما نتیجه‌ای که می‌خواهند را نمی‌گیرند؛ دلیل اصلی آن معمولاً نبود یک برنامه درسی دقیق و متناسب با پایه، رشته و هدف تحصیلی است. برنامه‌ریزی تحصیلی هوشمند نورتیکا با در نظر گرفتن پایه تحصیلی، رشته، رشته هدف دانشگاهی و حتی ساعت مطالعه روزانه‌ای که در اختیار داری، یک نقشه راه شخصی‌سازی‌شده می‌سازد تا وقت محدودت صرف مهم‌ترین درس‌ها و فصل‌ها شود، نه مطالعه پراکنده و بدون اولویت.</p>
  <p>برخلاف برنامه‌های درسی ثابت و از‌پیش‌آماده که برای همه دانش‌آموزان یکسان است، هوش مصنوعی نورتیکا با توجه به رشته هدف دانشگاهی (مثلاً پزشکی، مهندسی کامپیوتر یا حقوق) به دروس مرتبط وزن بیشتری می‌دهد. این یعنی دانش‌آموزی که هدفش پزشکی است، در برنامه‌اش به زیست‌شناسی و شیمی زمان بیشتری اختصاص می‌گیرد؛ در حالی که دانش‌آموز علاقه‌مند به مهندسی کامپیوتر، تمرکز بیشتری روی ریاضی، حسابان و ریاضیات گسسته خواهد داشت. برای آشنایی بیشتر با این رویکرد، مقاله <a href="/blog/program-study">چگونه یک برنامه مطالعاتی مؤثر بچینیم</a> را هم بخوانید.</p>
</div>

<div class="card">
  <h2>نورتیکا چگونه کار می‌کند؟</h2>
  <p>مسیر استفاده از نورتیکا ساده و کاملاً آنلاین است و در چند مرحله طی می‌شود:</p>
  <ol style="padding-inline-start:20px;line-height:2;">
    <li><b>ثبت‌نام و مشخص‌کردن اطلاعات پایه:</b> نام، شماره تلفن، پایه تحصیلی (هفتم تا دوازدهم)، رشته و در صورت تمایل رشته و دانشگاه هدف را وارد می‌کنی.</li>
    <li><b>گفت‌وگو با هوش مصنوعی نورتیکا:</b> در <a href="/plan">صفحه برنامه درسی</a>، درخواستت را مثل یک پیام معمولی می‌نویسی؛ مثلاً «یک برنامه یک هفته‌ای برای فیزیک یازدهم می‌خوام» یا «برنامه‌ای برای جمع‌بندی کنکور تجربی می‌خوام».</li>
    <li><b>دریافت برنامه اختصاصی:</b> نورتیکا بر اساس تمام کتاب‌ها و فصل‌های همان پایه و رشته، یک برنامه روزانه با اولویت‌بندی هوشمند دروس برایت می‌سازد که می‌توانی آن را به‌صورت PDF فارسی هم دانلود کنی.</li>
    <li><b>ثبت ساعت مطالعه روزانه:</b> بعد از هر جلسه مطالعه، ساعت و درس مورد مطالعه را ثبت می‌کنی تا نمودار رشد و پیشرفتت به‌صورت بصری نمایش داده شود.</li>
    <li><b>شرکت در آزمون آنلاین:</b> در <a href="/exam">صفحه آزمون</a>، برای سنجش یادگیری، آزمون تستی یا تشریحی با سطح دلخواه (آسان، متوسط، سخت) می‌دهی و پاسخ‌های غلطت با تحلیل هوش مصنوعی بررسی می‌شود.</li>
    <li><b>حضور در رتبه‌بندی:</b> بر اساس ساعات مطالعه و نتایج آزمون‌ها در <a href="/leaderboard">جدول رتبه‌بندی نورتیکا</a> قرار می‌گیری و نفرات برتر جایزه می‌گیرند.</li>
  </ol>
</div>

<div class="card">
  <h2>پوشش کامل کتاب‌های درسی متوسطه اول (پایه هفتم، هشتم و نهم)</h2>
  <p>برنامه‌ریزی و آزمون‌های نورتیکا برای دوره متوسطه اول تمام کتاب‌های درسی مصوب را به‌طور کامل و فصل‌به‌فصل پوشش می‌دهد: ریاضی، علوم تجربی، فارسی، عربی، دین و زندگی، مطالعات اجتماعی و زبان انگلیسی. برای هر پایه، سرفصل‌های اصلی هر کتاب در نظر گرفته می‌شود؛ برای نمونه در ریاضی هفتم مباحثی مثل راهبردهای حل مسئله، عددهای صحیح، جبر و معادله و هندسه و استدلال پوشش داده می‌شود و همین‌طور در پایه‌های هشتم و نهم به‌ترتیب مباحث پیشرفته‌تری از جمله عددهای گویا، چندضلعی‌ها، مجموعه‌ها و توان و جذر گنجانده شده است.</p>
  <p>در علوم تجربی نیز از اندازه‌گیری در علوم و سلول و بافت در پایه هفتم تا الکتریسیته و تنظیم عصبی در پایه هشتم و زمین‌شناسی و وراثت در پایه نهم، همه فصل‌ها در برنامه‌ریزی نورتیکا لحاظ می‌شوند. جزئیات کامل کتاب‌های هر پایه را می‌توانی در بخش «پوشش کامل کتاب‌های درسی» <a href="/plan">صفحه برنامه‌ریزی</a> ببینی.</p>
</div>

<div class="card">
  <h2>پوشش کامل کتاب‌های درسی متوسطه دوم (پایه دهم، یازدهم و دوازدهم)</h2>
  <p>برای دوره متوسطه دوم، نورتیکا به‌تفکیک هر رشته، تمام کتاب‌های تخصصی و عمومی را پوشش می‌دهد:</p>
  <ul style="padding-inline-start:20px;line-height:2;">
    <li><b>ریاضی فیزیک:</b> ریاضی، هندسه، حسابان، فیزیک، شیمی، ریاضیات گسسته، به‌همراه دروس عمومی مثل فارسی، عربی، دین و زندگی و زبان انگلیسی در هر سه پایه.</li>
    <li><b>علوم تجربی:</b> زیست‌شناسی، شیمی، فیزیک، ریاضی، زمین‌شناسی و دروس عمومی؛ با تمرکز ویژه روی فصل‌هایی مثل تقسیم یاخته، ژنتیک و تکامل در پایه دوازدهم که برای کنکور تجربی اهمیت بالایی دارند.</li>
    <li><b>علوم انسانی:</b> ادبیات فارسی، عربی، دین و زندگی، فلسفه، منطق، روان‌شناسی، جامعه‌شناسی، تاریخ، جغرافیا، اقتصاد و ریاضی و آمار.</li>
    <li><b>فنی‌حرفه‌ای:</b> دانش فنی پایه و تخصصی، کارگاه نوآوری و کارآفرینی، کارگاه پروژه‌محور و پروژه پایانی، در کنار دروس عمومی مشترک.</li>
  </ul>
  <p>همه این کتاب‌ها با سرفصل‌های دقیق فصل‌به‌فصل در موتور برنامه‌ریزی و طراحی آزمون نورتیکا تعریف شده‌اند تا هیچ بخشی از کتاب درسی از قلم نیفتد.</p>
</div>

<div class="card">
  <h2>آزمون آنلاین تستی و تشریحی با تحلیل هوش مصنوعی</h2>
  <p>در کنار برنامه‌ریزی، سنجش میزان یادگیری هم بخش مهمی از مسیر تحصیلی است. نورتیکا امکان طراحی آزمون آنلاین به دو شکل تستی (چهارگزینه‌ای) و تشریحی (تایپی) را در سه سطح آسان، متوسط و سخت فراهم می‌کند. تعداد سوال‌ها هم قابل انتخاب است (۵ تا ۲۰ سوال) تا بتوانی متناسب با زمانی که داری، یک آزمون کوتاه مروری یا یک آزمون جامع‌تر بدهی.</p>
  <p>نکته مهم درباره آزمون‌های نورتیکا، تحلیل هوشمند پاسخ‌های غلط است؛ به‌جای اینکه فقط نمره نهایی را ببینی، دلیل اشتباهت و نکته آموزشی مرتبط با آن سوال هم برایت توضیح داده می‌شود تا در دفعه بعد همان اشتباه تکرار نشود. تفاوت کامل آزمون تستی و تشریحی را هم می‌توانی در مقاله <a href="/blog/exam">راهنمای کامل آزمون آنلاین</a> بخوانی.</p>
</div>

<div class="card">
  <h2>رتبه‌بندی و جایزه؛ انگیزه مضاعف برای مطالعه مستمر</h2>
  <p>یکی از چالش‌های اصلی مطالعه، حفظ انگیزه در طول زمان است. نورتیکا با جدول رتبه‌بندی زنده، ساعات مطالعه ثبت‌شده و میانگین نمرات آزمون هر دانش‌آموز را نمایش می‌دهد و در پایان هر دوره، به سه نفر برتر جایزه نمادین تعلق می‌گیرد. این فضای رقابتی سالم، به‌خصوص برای دانش‌آموزانی که در آستانه کنکور یا امتحانات نهایی هستند، کمک می‌کند تا مطالعه را به یک عادت روزانه پایدار تبدیل کنند. <a href="/leaderboard">جدول رتبه‌بندی زنده نورتیکا را ببین</a>.</p>
</div>

<div class="card">
  <h2>۱۰ نکته کاربردی برای برنامه‌ریزی درسی مؤثر</h2>
  <ol style="padding-inline-start:20px;line-height:2;">
    <li>هر روز، قبل از شروع مطالعه، اول ببین طبق برنامه نورتیکا نوبت کدام درس و فصل است.</li>
    <li>به‌جای مطالعه پیوسته چند ساعته، از تکنیک مطالعه بلوکی (مثلاً ۵۰ دقیقه مطالعه و ۱۰ دقیقه استراحت) استفاده کن.</li>
    <li>بعد از پایان هر فصل، حتماً یک آزمون کوتاه از همان مبحث در نورتیکا بده تا یادگیری‌ات را بسنجی.</li>
    <li>ساعت مطالعه واقعی‌ات را همان روز ثبت کن، نه چند روز بعد؛ این کار دقت نمودار پیشرفتت را بالا می‌برد.</li>
    <li>دروسی که در برنامه اختصاصی‌ات وزن بیشتری دارند (بر اساس رشته هدف دانشگاهی‌ات) را در ساعات اوج تمرکز روزت بخوان.</li>
    <li>هفته‌ای یک‌بار به جدول رتبه‌بندی سر بزن؛ نه برای مقایسه ناسالم، بلکه برای حفظ انگیزه.</li>
    <li>اگر در یک درس مدام نمره پایین می‌گیری، برنامه‌ات را در همان درس برای مرور بیشتر تنظیم کن.</li>
    <li>پیش از امتحانات نهایی یا کنکور، از حالت آزمون تشریحی هم استفاده کن تا مهارت پاسخ‌دهی تشریحی‌ات هم تقویت شود.</li>
    <li>برنامه هفتگی‌ات را با روزهای واقعی زندگی‌ات (مثل کلاس‌های فوق‌برنامه) هماهنگ کن؛ نورتیکا امکان انتخاب روزهای دلخواه هفته را می‌دهد.</li>
    <li>برنامه را دانلود و پرینت کن یا روی گوشی نگه‌دار تا همیشه در دسترس باشد و بتوانی جلوی درس‌های خوانده‌شده تیک بزنی.</li>
  </ol>
</div>

<div class="card">
  <h2>نورتیکا برای کنکور و آینده تحصیلی</h2>
  <p>نورتیکا فقط برای مرور نمرات ترم نیست؛ چون تمام سرفصل‌های کتاب‌های درسی متوسطه دوم به‌خصوص پایه دوازدهم را در بر می‌گیرد، از همان ابتدای دهم تا روزهای پایانی کنکور می‌توانی از آن به‌عنوان مسیر برنامه‌ریزی بلندمدت استفاده کنی. وزن‌دهی هوشمند دروس بر اساس رشته هدف دانشگاهی (مثل پزشکی، مهندسی، حقوق، روان‌شناسی یا معماری) کمک می‌کند از همان سال‌های اول دبیرستان، مسیر مطالعه‌ات را با هدف نهایی‌ات هماهنگ کنی، به‌جای اینکه فقط چند ماه قبل از کنکور شروع به جمع‌بندی فشرده کنی. برای جزئیات بیشتر مقاله <a href="/blog/konkur">برنامه‌ریزی برای کنکور از همین امروز</a> را بخوان، یا مستقیم <a href="/pricing">پلن‌های اشتراک</a> نورتیکا را ببین.</p>
</div>

""" + latest_posts_html + """

<div class="card" id="home-faq-card">
  <h2>سوالات متداول</h2>
  """ + _faq_list_html(HOME_FAQ) + """
</div>
"""
    script = """
function noortikaReturnPath() {
  let returnPath = "/plan";
  try {
    const savedPath = localStorage.getItem("noortika-return-path");
    if (savedPath) {
      returnPath = savedPath;
      localStorage.removeItem("noortika-return-path");
    }
  } catch (e) {}
  return returnPath;
}

function hideAllAuthCards() {
  document.getElementById("login-card").style.display = "none";
  document.getElementById("register-card").style.display = "none";
  document.getElementById("forgot-card").style.display = "none";
  document.getElementById("code-card").style.display = "none";
  document.getElementById("reset-card").style.display = "none";
}

function showLoginCard() {
  hideAllAuthCards();
  document.getElementById("login-card").style.display = "block";
  document.getElementById("login-card").scrollIntoView({ behavior: "smooth", block: "center" });
}

function showRegisterCard() {
  hideAllAuthCards();
  document.getElementById("register-card").style.display = "block";
  document.getElementById("register-card").scrollIntoView({ behavior: "smooth", block: "center" });
}

function showForgotCard() {
  hideAllAuthCards();
  document.getElementById("forgot-card").style.display = "block";
  document.getElementById("forgot-card").scrollIntoView({ behavior: "smooth", block: "center" });
}

function showCodeCard() {
  hideAllAuthCards();
  document.getElementById("code-card").style.display = "block";
  document.getElementById("code-card").scrollIntoView({ behavior: "smooth", block: "center" });
}

function showResetCard() {
  hideAllAuthCards();
  document.getElementById("reset-card").style.display = "block";
  document.getElementById("reset-card").scrollIntoView({ behavior: "smooth", block: "center" });
}

let noortikaResetEmail = "";
let noortikaResetCode = "";
let noortikaCodeTimerInterval = null;

function startResetCodeTimer(ttlSeconds) {
  const timerEl = document.getElementById("code-timer");
  const submitBtn = document.getElementById("code-submit-btn");
  const codeInput = document.getElementById("reset_code");
  const alertBox = document.getElementById("code-alert-box");

  if (noortikaCodeTimerInterval) clearInterval(noortikaCodeTimerInterval);
  let remaining = ttlSeconds;
  submitBtn.disabled = false;
  codeInput.disabled = false;
  alertBox.innerHTML = "";

  const render = () => {
    const m = String(Math.floor(remaining / 60)).padStart(2, "0");
    const s = String(remaining % 60).padStart(2, "0");
    timerEl.textContent = `${m}:${s}`;
  };
  render();

  noortikaCodeTimerInterval = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(noortikaCodeTimerInterval);
      timerEl.textContent = "۰۰:۰۰";
      submitBtn.disabled = true;
      codeInput.disabled = true;
      alertBox.innerHTML = `<div class="alert error">مهلت وارد کردن کد تمام شد. برای دریافت کد جدید روی «کد جدید بفرست» بزن.</div>`;
      return;
    }
    render();
  }, 1000);
}

document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get("auth_required") === "1") {
    const alertBox = document.getElementById("alert-box");
    alertBox.innerHTML = `<div class="alert error">برای ورود به این بخش از سایت، ابتدا وارد حساب کاربری‌ات شو. اگر حساب نداری، ثبت‌نام کن.</div>`;
    showLoginCard();
  }

  document.getElementById("show-register-link").addEventListener("click", (e) => {
    e.preventDefault();
    showRegisterCard();
  });

  document.getElementById("show-login-link").addEventListener("click", (e) => {
    e.preventDefault();
    showLoginCard();
  });

  document.getElementById("show-forgot-link").addEventListener("click", (e) => {
    e.preventDefault();
    showForgotCard();
  });

  document.getElementById("back-to-login-from-forgot").addEventListener("click", (e) => {
    e.preventDefault();
    showLoginCard();
  });

  document.getElementById("back-to-forgot-from-reset").addEventListener("click", (e) => {
    e.preventDefault();
    showForgotCard();
  });

  document.getElementById("resend-code-link").addEventListener("click", async (e) => {
    e.preventDefault();
    const alertBox = document.getElementById("code-alert-box");
    try {
      const data = await apiPost("/api/users/forgot-password", { email: noortikaResetEmail });
      alertBox.innerHTML = `<div class="alert success">${data.message}</div>`;
      startResetCodeTimer(data.ttl_seconds || 120);
    } catch (err) {
      alertBox.innerHTML = `<div class="alert error">${err.message}</div>`;
    }
  });
});

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const alertBox = document.getElementById("alert-box");
  alertBox.innerHTML = "";

  const payload = {
    phone: document.getElementById("login_phone").value,
    password: document.getElementById("login_password").value,
  };

  try {
    const data = await apiPost("/api/users/login", payload);
    setUserId(data.user_id);
    const returnPath = noortikaReturnPath();
    alertBox.innerHTML = `<div class="alert success">${data.message} در حال انتقال...</div>`;
    setTimeout(() => (window.location.href = returnPath), 900);
  } catch (err) {
    alertBox.innerHTML = `<div class="alert error">${err.message}</div>`;
    if (err.message && err.message.includes("ثبت‌نام")) {
      setTimeout(showRegisterCard, 1200);
    }
  }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const alertBox = document.getElementById("register-alert-box");
  alertBox.innerHTML = "";

  const payload = {
    full_name: document.getElementById("full_name").value,
    phone: document.getElementById("phone").value,
    email: document.getElementById("email").value,
    password: document.getElementById("password").value,
    grade: document.getElementById("grade").value,
    field: document.getElementById("field").value,
    target_major: document.getElementById("target_major").value,
    target_university: document.getElementById("target_university").value,
    daily_hours: parseFloat(document.getElementById("daily_hours").value),
  };

  try {
    const data = await apiPost("/api/users", payload);
    setUserId(data.user_id);
    const returnPath = noortikaReturnPath();
    alertBox.innerHTML = `<div class="alert success">با موفقیت ثبت‌نام شدید! در حال انتقال...</div>`;
    setTimeout(() => (window.location.href = returnPath), 900);
  } catch (err) {
    alertBox.innerHTML = `<div class="alert error">${err.message}</div>`;
    if (err.message && err.message.includes("قبلاً ثبت‌نام")) {
      setTimeout(showLoginCard, 1200);
    }
  }
});

document.getElementById("forgot-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const alertBox = document.getElementById("forgot-alert-box");
  alertBox.innerHTML = "";
  const emailVal = document.getElementById("forgot_email").value.trim();

  try {
    const data = await apiPost("/api/users/forgot-password", { email: emailVal });
    noortikaResetEmail = emailVal;
    alertBox.innerHTML = `<div class="alert success">${data.message}</div>`;
    document.getElementById("reset_code").value = "";
    setTimeout(() => {
      showCodeCard();
      startResetCodeTimer(data.ttl_seconds || 120);
    }, 700);
  } catch (err) {
    alertBox.innerHTML = `<div class="alert error">${err.message}</div>`;
  }
});

document.getElementById("code-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const alertBox = document.getElementById("code-alert-box");
  alertBox.innerHTML = "";
  const codeVal = document.getElementById("reset_code").value.trim();

  try {
    const data = await apiPost("/api/users/verify-reset-code", { email: noortikaResetEmail, code: codeVal });
    noortikaResetCode = codeVal;
    if (noortikaCodeTimerInterval) clearInterval(noortikaCodeTimerInterval);
    alertBox.innerHTML = `<div class="alert success">${data.message}</div>`;
    setTimeout(showResetCard, 600);
  } catch (err) {
    alertBox.innerHTML = `<div class="alert error">${err.message}</div>`;
  }
});

document.getElementById("reset-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const alertBox = document.getElementById("reset-alert-box");
  alertBox.innerHTML = "";

  const payload = {
    email: noortikaResetEmail,
    code: noortikaResetCode,
    new_password: document.getElementById("reset_new_password").value,
  };

  try {
    const data = await apiPost("/api/users/reset-password", payload);
    alertBox.innerHTML = `<div class="alert success">${data.message}</div>`;
    setTimeout(() => {
      showLoginCard();
      if (data.phone) document.getElementById("login_phone").value = data.phone;
      document.getElementById("login_password").focus();
    }, 1200);
  } catch (err) {
    alertBox.innerHTML = `<div class="alert error">${err.message}</div>`;
  }
});
"""
    return base_page(
        "نورتیکا | سایت تخصصی برنامه‌ریزی درسی و آزمون آنلاین با هوش مصنوعی",
        "/", body, script,
        meta_description="سایت تخصصی نورتیکا: ورود و ثبت‌نام سریع، برنامه‌ریزی درسی هوشمند، آزمون آنلاین تستی و تشریحی و رتبه‌بندی با جایزه برای دانش‌آموزان متوسطه اول و دوم؛ برنامه اختصاصی با هوش مصنوعی.",
        extra_schema=_faq_schema(HOME_FAQ),
    )


def plan_page() -> str:
    body = """
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js" defer></script>

<div class="hero">
  <h1>برنامه درسی هوشمند</h1>
  <p>با هوش مصنوعی نورتیکا مثل یک چت هوشمند صحبت کن و برنامه اختصاصی خودت رو بساز. برای اصول یک برنامه مطالعاتی مؤثر می‌تونی <a href="/blog/program-study">این مقاله</a> رو هم بخونی، و بعد از هر فصل حتماً یک <a href="/exam">آزمون آنلاین</a> کوتاه از همون مبحث بده.</p>
</div>

<div class="card">
  <h2>💬 بگو چه برنامه‌ای می‌خوای</h2>
  <p style="color:var(--text-muted);font-size:0.9rem;">مثلاً بنویس: «یک برنامه یک هفته‌ای برای فیزیک یازدهم می‌خوام» یا هر درخواست دیگه‌ای که مدنظرته.</p>
  <div id="chat-history" style="margin:12px 0;"></div>
  <div class="form-grid">
    <div class="field" style="grid-column:1/-1;">
      <label>پیام تو</label>
      <textarea id="chat_message" rows="3" placeholder="برنامه مدنظرت رو اینجا بنویس..."></textarea>
    </div>
  </div>
  <button id="chat-send-btn" class="btn" style="margin-top:10px;">ارسال به پشتیبان هوشمند نورتیکا</button>
  <div id="chat-alert-box"></div>

  <div style="margin-top:22px;border-top:1px dashed var(--card-border);padding-top:18px;">
    <h3>📅 روزها و بازه تاریخ برنامه</h3>
    <p style="color:var(--text-muted);font-size:0.85rem;">روزهایی از هفته که می‌خوای برات برنامه بچینه رو انتخاب کن (اختیاری؛ اگه چیزی انتخاب نکنی همه روزها لحاظ می‌شه).</p>
    <div id="weekday-checks" style="display:flex;flex-wrap:wrap;gap:8px;margin:10px 0;">
      <label class="badge-note" style="cursor:pointer;"><input type="checkbox" value="شنبه" class="weekday-cb" /> شنبه</label>
      <label class="badge-note" style="cursor:pointer;"><input type="checkbox" value="یکشنبه" class="weekday-cb" /> یکشنبه</label>
      <label class="badge-note" style="cursor:pointer;"><input type="checkbox" value="دوشنبه" class="weekday-cb" /> دوشنبه</label>
      <label class="badge-note" style="cursor:pointer;"><input type="checkbox" value="سه‌شنبه" class="weekday-cb" /> سه‌شنبه</label>
      <label class="badge-note" style="cursor:pointer;"><input type="checkbox" value="چهارشنبه" class="weekday-cb" /> چهارشنبه</label>
      <label class="badge-note" style="cursor:pointer;"><input type="checkbox" value="پنجشنبه" class="weekday-cb" /> پنجشنبه</label>
      <label class="badge-note" style="cursor:pointer;"><input type="checkbox" value="جمعه" class="weekday-cb" /> جمعه</label>
    </div>
    <div class="form-grid">
      <div class="field">
        <label>از تاریخ (شمسی)</label>
        <div style="display:flex;gap:6px;">
          <select id="start_jy" style="flex:1;"></select>
          <select id="start_jm" style="flex:1;"></select>
          <select id="start_jd" style="flex:1;"></select>
        </div>
        <input type="hidden" id="plan_start_date" />
      </div>
      <div class="field">
        <label>تا تاریخ (شمسی)</label>
        <div style="display:flex;gap:6px;">
          <select id="end_jy" style="flex:1;"></select>
          <select id="end_jm" style="flex:1;"></select>
          <select id="end_jd" style="flex:1;"></select>
        </div>
        <input type="hidden" id="plan_end_date" />
      </div>
    </div>
  </div>

  <div style="margin-top:20px;">
    <h3>افزودن درس دلخواه (اختیاری)</h3>
    <div id="custom-lessons-list"></div>
    <div class="form-grid">
      <div class="field">
        <label>نام درس</label>
        <input type="text" id="custom_lesson_name" placeholder="مثلاً کارگاه کارآفرینی" />
      </div>
      <div class="field">
        <label>موضوعات (با کاما جدا کنید)</label>
        <input type="text" id="custom_lesson_topics" placeholder="مثلاً مبحث ۱, مبحث ۲" />
      </div>
    </div>
    <button type="button" id="add-lesson-btn" class="btn secondary" style="margin-top:10px;">+ افزودن درس</button>
  </div>

  <div style="margin-top:24px;">
    <button id="generate-btn" class="btn">ساخت برنامه درسی هوشمند نورتیکا</button>
  </div>
  <div id="alert-box"></div>
</div>

<div id="advice-card" class="card" style="display:none;">
  <h3>💡 تحلیل و توصیه اختصاصی هوش مصنوعی</h3>
  <p id="advice-text"></p>
</div>

<div id="chart-card" class="card" style="display:none;">
  <h3>📊 توزیع دروس در برنامه</h3>
  <div style="max-width:320px;margin:0 auto;">
    <canvas id="subject-pie-chart"></canvas>
  </div>
</div>

<div id="growth-card" class="card" style="display:none;">
  <h3>📈 جدول رشد پیش‌بینی‌شده</h3>
  <div id="growth-table-container"></div>
</div>

<div id="pdf-card" class="card" style="display:none;text-align:center;">
  <button id="download-pdf-btn" class="btn gold">⬇️ دانلود برنامه به‌صورت PDF فارسی</button>
</div>

<div class="card">
  <h3>ثبت ساعت مطالعه امروز</h3>
  <div style="display:flex;flex-wrap:wrap;gap:24px;align-items:center;">
    <div style="flex:1;min-width:220px;">
      <div class="form-grid">
        <div class="field">
          <label>تعداد ساعت</label>
          <input type="number" id="log_hours" min="0" step="0.25" />
        </div>
        <div class="field">
          <label>درس (اختیاری)</label>
          <input type="text" id="log_subject" />
        </div>
      </div>
      <button id="log-btn" class="btn secondary" style="margin-top:12px;">ثبت مطالعه</button>
      <span id="log-msg" class="badge-note" style="display:none;"></span>
    </div>
    <div style="text-align:center;">
      <div id="brain-wrap" style="position:relative;width:130px;height:130px;margin:0 auto;">
        <img src="/brain.png" alt="مغز نورتیکا" style="position:absolute;top:0;left:0;width:130px;height:130px;object-fit:contain;opacity:0.35;filter:grayscale(1);" />
        <div id="brain-fill-mask" style="position:absolute;bottom:0;left:0;width:130px;height:0%;overflow:hidden;transition:height 1.1s ease;">
          <img src="/brain.png" alt="" style="position:absolute;bottom:0;left:0;width:130px;height:130px;object-fit:contain;filter:drop-shadow(0 0 8px rgba(124,58,237,0.55));" />
        </div>
      </div>
      <div id="brain-percent-label" style="font-weight:800;color:var(--primary);margin-top:4px;">۰٪ پر شده</div>
      <div style="font-size:0.75rem;color:var(--text-muted);">میزان پر شدن مغز امروزت 🧠</div>
    </div>
  </div>
</div>

<div id="schedule-container"></div>

<div class="card">
  <h2>📚 پوشش کامل کتاب‌های درسی متوسطه اول و دوم</h2>
  <p style="color:var(--text-muted);font-size:0.9rem;">برنامه‌ریزی نورتیکا تمام کتاب‌های پایه هفتم تا دوازدهم (همه رشته‌ها) را به‌طور کامل و فصل‌به‌فصل پوشش می‌دهد؛ برای داوطلبان کنکور هم پیشنهاد می‌کنیم مقاله <a href="/blog/konkur">برنامه‌ریزی برای کنکور</a> را بخوانید:</p>
  """ + _course_catalog_html() + """
  <p style="margin-top:14px;font-size:0.85rem;color:var(--text-muted);">برای دسترسی به امکانات کامل‌تر، پلن‌های <a href="/pricing">اشتراک نورتیکا</a> را هم ببینید.</p>
</div>
"""
    return base_page(
        "برنامه‌ریزی درسی هوشمند با هوش مصنوعی | نورتیکا",
        "/plan", body, PLAN_JS,
        meta_description="ساخت برنامه مطالعاتی اختصاصی با هوش مصنوعی نورتیکا؛ چت کن، روز و تاریخ دلخواهت را انتخاب کن و خروجی PDF فارسی بگیر.",
        extra_schema=_course_schema(),
    )


def exam_page() -> str:
    body = """
<div class="hero">
  <h1>آزمون تستی شبیه‌ساز کنکور</h1>
  <p>درس و تعداد سوال دلخواهت را انتخاب کن؛ هوش مصنوعی نورتیکا برایت آزمون طراحی می‌کند. اگر نمی‌دونی تستی بهتره یا تشریحی، <a href="/blog/exam">این راهنما</a> رو بخون؛ و برای هماهنگ‌کردن آزمون‌ها با برنامه مطالعاتی‌ات هم به <a href="/plan">صفحه برنامه درسی</a> سر بزن.</p>
</div>

<div class="card" id="setup-card">
  <div class="form-grid">
    <div class="field">
      <label>پایه تحصیلی</label>
      <select id="exam_grade">
        <option value="هفتم">هفتم</option>
        <option value="هشتم">هشتم</option>
        <option value="نهم">نهم</option>
        <option value="دهم">دهم</option>
        <option value="یازدهم">یازدهم</option>
        <option value="دوازدهم">دوازدهم</option>
      </select>
    </div>
    <div class="field">
      <label>رشته</label>
      <select id="exam_field">
        <option value="عمومی">عمومی (متوسطه اول)</option>
        <option value="ریاضی فیزیک">ریاضی فیزیک</option>
        <option value="علوم تجربی">علوم تجربی</option>
        <option value="علوم انسانی">علوم انسانی</option>
        <option value="فنی حرفه‌ای">فنی حرفه‌ای</option>
      </select>
    </div>
    <div class="field">
      <label>درس</label>
      <select id="exam_subject"></select>
    </div>
    <div class="field">
      <label>فصل (اختیاری)</label>
      <select id="exam_lesson">
        <option value="">همه فصل‌ها</option>
      </select>
    </div>
    <div class="field">
      <label>سطح سختی</label>
      <select id="exam_difficulty">
        <option value="آسان">آسان</option>
        <option value="متوسط" selected>متوسط</option>
        <option value="سخت">سخت</option>
      </select>
    </div>
    <div class="field">
      <label>نوع سوالات</label>
      <select id="exam_type">
        <option value="تستی" selected>تستی (چهارگزینه‌ای)</option>
        <option value="تشریحی">تشریحی (تایپی)</option>
      </select>
    </div>
    <div class="field">
      <label>تعداد سوال</label>
      <select id="exam_count">
        <option value="5">۵ سوال</option>
        <option value="10" selected>۱۰ سوال</option>
        <option value="15">۱۵ سوال</option>
        <option value="20">۲۰ سوال</option>
      </select>
    </div>
  </div>
  <button id="start-exam-btn" class="btn" style="margin-top:16px;">شروع آزمون</button>
  <div id="alert-box"></div>
</div>

<div id="quiz-container"></div>

<div id="result-card" class="card" style="display:none;">
  <h3>نتیجه آزمون</h3>
  <p id="result-text"></p>
  <div id="wrong-analysis-container"></div>
</div>

<div class="card" style="font-size:0.85rem;color:var(--text-muted);">
  بعد از هر آزمون، جایگاهت رو توی <a href="/leaderboard">جدول رتبه‌بندی نورتیکا</a> ببین.
</div>
"""
    return base_page(
        "آزمون آنلاین تستی و تشریحی با تحلیل هوش مصنوعی | نورتیکا",
        "/exam", body, EXAM_JS,
        meta_description="آزمون‌های تستی و تشریحی متوسطه اول و دوم با سطح آسان تا سخت و تحلیل هوشمند پاسخ‌های غلط توسط هوش مصنوعی نورتیکا.",
    )


def consultation_page() -> str:
    body = """
<div class="hero">
  <h1>مشاوره تحصیلی هوشمند نورتیکا</h1>
  <p>هر سوالی درباره درس، رشته، استرس امتحان یا مسیر آینده‌ات داری، اینجا بپرس. مشاوره تحصیلی هوشمند نورتیکا کنارته تا با هم بررسیش کنیم.</p>
</div>

<div class="card">
  <div id="consult-history" style="min-height:200px;max-height:520px;overflow-y:auto;margin-bottom:14px;"></div>
  <div class="form-grid">
    <div class="field" style="grid-column:1/-1;">
      <label>پیام تو</label>
      <textarea id="consult_message" rows="3" placeholder="مثلاً: نمی‌دونم برای کنکور رشته ریاضی بخونم یا تجربی، استرس دارم..."></textarea>
    </div>
  </div>
  <button id="consult-send-btn" class="btn" style="margin-top:10px;">ارسال پیام</button>
  <div id="consult-alert-box"></div>
</div>

<div class="card" style="font-size:0.85rem;color:var(--text-muted);">
  اگه دنبال مسیر دقیق رشته و دانشگاه هستی، بعد از این گفت‌وگو سری هم به <a href="/major-selection">انتخاب رشته هوشمند نورتیکا</a> بزن.
</div>
"""
    return base_page(
        "مشاوره تحصیلی هوشمند نورتیکا | چت با مشاور هوشمند",
        "/consultation", body, CONSULT_JS,
        meta_description="مشاوره تحصیلی هوشمند نورتیکا: گفت‌وگوی گرم و دلسوزانه درباره درس، رشته، استرس امتحان و مسیر آینده تحصیلی، همراه با راهنمایی شخصی‌سازی‌شده.",
    )


def major_selection_page() -> str:
    body = """
<div class="hero">
  <h1>انتخاب رشته هوشمند نورتیکا</h1>
  <p>بر اساس رتبه، معدل و رشته مورد علاقه‌ات، دانشگاه‌های مناسب (دولتی، آزاد و غیرانتفاعی) رو پیدا می‌کنیم — هم به‌صورت متن، هم فایل PDF.</p>
</div>

<div class="card">
  <h2>🎓 اطلاعاتت رو وارد کن</h2>
  <div class="form-grid">
    <div class="field">
      <label>نام و نام‌خانوادگی</label>
      <input type="text" id="ms_full_name" required />
    </div>
    <div class="field">
      <label>پایه تحصیلی</label>
      <select id="ms_grade">
        <option>دوازدهم</option>
        <option>فارغ‌التحصیل</option>
        <option>یازدهم</option>
      </select>
    </div>
    <div class="field">
      <label>نمره دیپلم</label>
      <input type="number" id="ms_diploma_rank" min="0" max="20" step="0.01" required />
    </div>
    <div class="field">
      <label>رتبه کنکور</label>
      <input type="number" id="ms_konkur_rank" min="1" required />
    </div>
    <div class="field">
      <label>رشته مورد نظر</label>
      <input type="text" id="ms_target_field" required placeholder="مثلاً پزشکی، مهندسی کامپیوتر..." />
    </div>
    <div class="field">
      <label>شهر مورد نظر</label>
      <input type="text" id="ms_target_city" required placeholder="مثلاً تهران" />
    </div>
  </div>
  <div class="field">
    <label>آپلود کارنامه یا دفترچه انتخاب رشته (اختیاری — PDF)</label>
    <input type="file" id="ms_file" accept="application/pdf" />
  </div>
  <button id="ms-submit-btn" class="btn" style="margin-top:10px;">پیدا کردن دانشگاه‌های مناسب</button>
  <div id="ms-alert-box"></div>
</div>

<div id="ms-result-container"></div>
"""
    return base_page(
        "انتخاب رشته هوشمند نورتیکا | پیشنهاد دانشگاه بر اساس رتبه",
        "/major-selection", body, MAJOR_JS,
        meta_description="انتخاب رشته هوشمند نورتیکا: با وارد کردن نمره دیپلم، رتبه کنکور، رشته و شهر مورد نظر، دانشگاه‌های دولتی، آزاد و غیرانتفاعی مناسب پیدا کن و خروجی PDF و متنی بگیر.",
    )


def leaderboard_page() -> str:
    body = """
<div class="hero">
  <h1>رتبه‌بندی نورتیکا 🏆</h1>
  <p>بر اساس ساعات مطالعه ثبت‌شده و نتایج آزمون‌ها؛ نفرات اول تا سوم جایزه می‌گیرند! برای بالا رفتن از رتبه‌بندی، اول یک <a href="/plan">برنامه درسی هوشمند</a> بساز و بعد از هر فصل <a href="/exam">آزمون آنلاین</a> بده تا ساعات مطالعه و نمراتت ثبت شود.</p>
</div>

<div id="leaderboard-container" class="card"></div>

<div class="card" style="font-size:0.85rem;color:var(--text-muted);">
  می‌خوای بدونی چطور با انگیزه بیشتری مطالعه کنی؟ مقاله <a href="/blog/konkur">برنامه‌ریزی برای کنکور از همین امروز</a> رو بخون.
</div>
"""
    script = """
document.addEventListener("DOMContentLoaded", async () => {
  const container = document.getElementById("leaderboard-container");
  try {
    const res = await apiGet("/api/leaderboard");
    if (!res.leaderboard.length) {
      container.innerHTML = "<p>هنوز کسی در رتبه‌بندی ثبت نشده است. شروع کن!</p>";
      return;
    }
    container.innerHTML = res.leaderboard
      .map((u) => {
        const topClass = u.rank <= 3 ? `top-${u.rank}` : "";
        const medal = u.rank === 1 ? "🥇" : u.rank === 2 ? "🥈" : u.rank === 3 ? "🥉" : "";
        return `
        <div class="leader-row ${topClass}">
          <div style="display:flex;align-items:center;gap:14px;">
            <span class="rank-badge">${u.rank}</span>
            <div>
              <div><b>${u.full_name}</b> ${medal}</div>
              <div style="font-size:0.8rem;color:var(--text-muted);">${u.field} - پایه ${u.grade}</div>
            </div>
          </div>
          <div style="text-align:left;">
            <div>⏱ ${u.total_hours} ساعت مطالعه</div>
            <div style="font-size:0.8rem;color:var(--text-muted);">میانگین آزمون: ${u.avg_score}%</div>
            ${u.prize ? `<div class="badge-note">🎁 جایزه: ${u.prize}</div>` : ""}
          </div>
        </div>`;
      })
      .join("");
  } catch (err) {
    container.innerHTML = `<div class="alert error">${err.message}</div>`;
  }
});
"""
    return base_page(
        "رتبه‌بندی دانش‌آموزان نورتیکا",
        "/leaderboard", body, script,
        meta_description="جدول رتبه‌بندی دانش‌آموزان فعال نورتیکا بر اساس ساعت مطالعه و نتایج آزمون‌ها.",
    )


def pricing_page() -> str:
    body = """
<div class="hero">
  <h1>پلن‌های اشتراک نورتیکا</h1>
  <p>پرداخت در این نسخه به صورت نمادین (آزمایشی) انجام می‌شود. قبل از انتخاب پلن، می‌تونی اول رایگان از <a href="/plan">برنامه‌ریزی درسی هوشمند</a> و <a href="/exam">آزمون آنلاین</a> استفاده کنی.</p>
</div>

<div class="pricing-grid" id="pricing-grid"></div>
<div id="alert-box" class="card" style="display:none;"></div>

<div class="card" style="font-size:0.85rem;color:var(--text-muted);">
  سوالی درباره پلن‌ها داری؟ به <a href="/support">صفحه پشتیبانی</a> سر بزن.
</div>
"""
    script = """
document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("pricing-grid");
  try {
    const res = await apiGet("/api/subscription/plans");
    grid.innerHTML = res.plans
      .map(
        (p) => `
      <div class="price-card">
        <h3>${p.title}</h3>
        <div class="price">${p.price_label}</div>
        <p style="color:var(--text-muted);font-size:0.9rem;">${p.description}</p>
        <button class="btn ${p.price === 0 ? "secondary" : "gold"} subscribe-btn" data-plan="${p.id}">
          ${p.price === 0 ? "شروع رایگان" : "خرید نمادین"}
        </button>
      </div>`
      )
      .join("");

    document.querySelectorAll(".subscribe-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const userId = getUserId();
        const alertBox = document.getElementById("alert-box");
        alertBox.style.display = "block";
        if (!userId) {
          alertBox.innerHTML = `<div class="alert error">لطفاً ابتدا ثبت‌نام کن.</div>`;
          return;
        }
        try {
          const data = await apiPost("/api/subscription/subscribe", {
            user_id: parseInt(userId),
            plan_id: btn.dataset.plan,
          });
          alertBox.innerHTML = `<div class="alert success">${data.message}</div>`;
        } catch (err) {
          alertBox.innerHTML = `<div class="alert error">${err.message}</div>`;
        }
      });
    });
  } catch (err) {
    grid.innerHTML = `<div class="alert error">${err.message}</div>`;
  }
});
"""
    return base_page(
        "طرح‌های اشتراک نورتیکا",
        "/pricing", body, script,
        meta_description="طرح‌های اشتراک سایت تخصصی نورتیکا برای دسترسی کامل به برنامه‌ریزی درسی و آزمون آنلاین.",
    )


def support_page() -> str:
    body = """
<div class="hero">
  <h1>پشتیبانی نورتیکا</h1>
  <p>سوالی داری؟ از راه‌های ارتباطی زیر با ما در تماس باش یا پاسخ سوالات پرتکرار را ببین. برای آموزش‌های بیشتر هم می‌تونی سری به <a href="/blog">وبلاگ نورتیکا</a> بزنی، یا مستقیماً از <a href="/plan">برنامه‌ریزی درسی</a> و <a href="/pricing">پلن‌های اشتراک</a> شروع کنی.</p>
</div>

<div class="card" id="contact-info-card" style="display:none;">
  <h3>راه‌های ارتباط با پشتیبانی</h3>
  <div class="pricing-grid" id="contact-info-grid"></div>
</div>

<div class="card" id="faq-card">
  <h3>سوالات پرتکرار</h3>
  <div id="faq-list">""" + _faq_list_html(SUPPORT_FAQ) + """</div>
</div>
"""
    script = """
(async () => {
  try {
    const res = await apiGet("/api/support/faq");
    document.getElementById("faq-list").innerHTML = res.faq
      .map((f) => `<div class="day-card"><b>${f.q}</b><p style="margin:8px 0 0;color:var(--text-muted);">${f.a}</p></div>`)
      .join("");
  } catch (e) {}
})();

(async () => {
  try {
    const info = await apiGet("/api/support/contact-info");
    const items = [
      { icon: "📍", title: "آدرس دفتر پشتیبانی", value: info.office_address, link: false },
      { icon: "☎️", title: "شماره تلفن پشتیبانی", value: info.company_phone, link: false },
      { img: "/icons/bale.png", title: "کانال بله", value: info.bale_channel, link: true },
      { img: "/icons/telegram.png", title: "کانال تلگرام", value: info.telegram_channel, link: true },
      { img: "/icons/instagram.png", title: "پیج اینستاگرام", value: info.instagram_channel, link: true },
    ];
    const cards = items
      .filter((it) => it.value)
      .map((it) => `
        <div class="price-card">
          <div style="font-size:1.8rem;">${it.img ? `<img src="${it.img}" alt="${it.title}" style="width:40px;height:40px;border-radius:10px;object-fit:cover;" />` : it.icon}</div>
          <div style="font-weight:700;">${it.title}</div>
          <div style="color:var(--text-muted);font-size:0.9rem;word-break:break-word;">
            ${it.link ? `<a href="${it.value}" target="_blank" rel="noopener">${it.value}</a>` : it.value}
          </div>
        </div>`)
      .join("");
    if (cards) {
      document.getElementById("contact-info-grid").innerHTML = cards;
      document.getElementById("contact-info-card").style.display = "block";
    }
  } catch (e) {}
})();
"""
    return base_page(
        "پشتیبانی و پرسش‌های متداول | نورتیکا",
        "/support", body, script,
        meta_description="پاسخ سوالات متداول، راه‌های ارتباطی (تلفن، تلگرام، بله، اینستاگرام) و پشتیبانی سایت تخصصی نورتیکا درباره برنامه‌ریزی درسی، آزمون آنلاین و اشتراک.",
        extra_schema=_faq_schema(SUPPORT_FAQ),
    )


# ---------------------------------------------------------------------------
# وبلاگ
# ---------------------------------------------------------------------------

BLOG_POSTS = {
    "program-study": {
        "title": "چگونه یک برنامه مطالعاتی مؤثر بچینیم؟ راهنمای کامل برنامه‌ریزی درسی",
        "description": "چرا اکثر برنامه‌های درسی دوام نمی‌آورند و یک برنامه مطالعاتی مؤثر و واقع‌بینانه چه ویژگی‌هایی دارد؛ با راهکارهای عملی و نقش هوش مصنوعی در برنامه‌ریزی شخصی‌سازی‌شده.",
        "category": "برنامه‌ریزی درسی",
        "published": "2026-06-01",
        "modified": "2026-07-01",
        "body_html": """
<p>خیلی از دانش‌آموزان حداقل یک‌بار برای خودشان برنامه درسی نوشته‌اند؛ برنامه‌ای پر از جدول‌های رنگی و ساعت‌های دقیق که معمولاً بعد از چند روز کنار گذاشته می‌شود. سؤال اصلی این است: چرا اکثر برنامه‌های درسی دوام نمی‌آورند و چطور می‌شود یک برنامه مطالعاتی ساخت که واقعاً اجرا شود؟</p>

<h2>چرا اکثر برنامه‌های درسی شکست می‌خورند؟</h2>
<p>رایج‌ترین اشتباه، نوشتن برنامه‌ای غیرواقع‌بینانه است؛ مثلاً در نظر گرفتن ۸ ساعت مطالعه فشرده برای دانش‌آموزی که در طول هفته کلاس و فعالیت‌های دیگر هم دارد. اشتباه دوم، نادیده‌گرفتن اولویت‌بندی دروس بر اساس هدف تحصیلی است؛ وقتی همه درس‌ها وزن یکسان دارند، وقت محدود صرف مباحثی می‌شود که اهمیت کمتری برای هدف نهایی دانش‌آموز دارند.</p>

<h2>اصول یک برنامه مطالعاتی خوب</h2>
<p>یک برنامه مطالعاتی مؤثر باید سه ویژگی داشته باشد: واقع‌بینانه بودن (متناسب با ساعت واقعی در دسترس)، اولویت‌بندی‌شده بودن (بر اساس پایه، رشته و هدف دانشگاهی) و قابل سنجش بودن (یعنی بعد از هر فصل، بازخوردی از میزان یادگیری وجود داشته باشد). دقیقاً به همین دلیل است که بعد از هر بخش از برنامه، پیشنهاد می‌شود یک <a href="/exam">آزمون آنلاین</a> کوتاه از همان مبحث گرفته شود.</p>

<h2>نقش هوش مصنوعی در برنامه‌ریزی شخصی‌سازی‌شده</h2>
<p>برنامه‌ریزی دستی معمولاً وزن دروس را به‌درستی تنظیم نمی‌کند، اما وقتی هوش مصنوعی پایه تحصیلی، رشته و رشته هدف دانشگاهی را می‌داند، می‌تواند فصل‌های مهم‌تر را شناسایی کند و زمان بیشتری به آن‌ها اختصاص دهد. برای تجربه این نوع برنامه‌ریزی می‌توانی از <a href="/plan">صفحه برنامه درسی هوشمند نورتیکا</a> شروع کنی و مستقیماً با هوش مصنوعی درباره برنامه دلخواهت صحبت کنی.</p>

<h2>جمع‌بندی</h2>
<p>برنامه مطالعاتی خوب، برنامه‌ای است که با زندگی واقعی دانش‌آموز همخوانی دارد، دروس مهم‌تر را در اولویت می‌گذارد و همراه با سنجش دوره‌ای پیش می‌رود. اگر می‌خواهی همین رویکرد را برای <a href="/blog/konkur">جمع‌بندی کنکور</a> یا آماده‌شدن برای <a href="/blog/exam">آزمون‌های آنلاین</a> به کار بگیری، می‌توانی مقالات مرتبط را هم مطالعه کنی یا از طریق <a href="/support">صفحه پشتیبانی</a> سؤالت را بپرسی.</p>
""",
    },
    "exam": {
        "title": "راهنمای کامل آزمون آنلاین: تستی بهتر است یا تشریحی؟",
        "description": "تفاوت آزمون تستی و تشریحی، نقش سطح سختی و تعداد سوال در سنجش دقیق‌تر یادگیری، و اینکه تحلیل هوش مصنوعی پاسخ‌های غلط چه کمکی به پیشرفت تحصیلی می‌کند.",
        "category": "آزمون آنلاین",
        "published": "2026-06-10",
        "modified": "2026-07-01",
        "body_html": """
<p>آزمون دادن فقط برای گرفتن نمره نیست؛ یکی از مؤثرترین روش‌های یادگیری همان «یادآوری فعال» (Active Recall) است که از طریق آزمون‌های دوره‌ای اتفاق می‌افتد. اما سؤال رایج این است: آزمون تستی بهتر است یا تشریحی، و چند سوال کافی است؟</p>

<h2>تفاوت آزمون تستی و تشریحی</h2>
<p>آزمون تستی (چهارگزینه‌ای) سرعت مرور مطالب و شناسایی سریع نقاط ضعف را بالا می‌برد و برای مرور روزانه یا هفتگی مناسب‌تر است. آزمون تشریحی (تایپی) در مقابل، عمق درک مطلب و توانایی توضیح‌دادن را می‌سنجد و برای آمادگی امتحانات نهایی و برخی سؤالات کنکور که نیاز به تحلیل دارند، اهمیت بیشتری دارد. بهترین رویکرد، ترکیب هر دو نوع در طول مسیر مطالعه است.</p>

<h2>سطح سختی و تعداد سوال را چطور انتخاب کنیم؟</h2>
<p>برای شروع یک مبحث تازه، سطح آسان تا متوسط با ۵ تا ۱۰ سوال کافی است؛ اما برای جمع‌بندی نهایی یک فصل یا آماده‌شدن برای <a href="/blog/konkur">کنکور</a>، بهتر است سطح سخت و تعداد سوال بیشتر (۱۵ تا ۲۰ سوال) انتخاب شود تا واقعاً آماده‌بودن سنجیده شود. می‌توانی همین حالا از <a href="/exam">صفحه آزمون آنلاین نورتیکا</a> با تنظیم دلخواه شروع کنی.</p>

<h2>چرا تحلیل هوش مصنوعی پاسخ‌های غلط مهم است؟</h2>
<p>نمره به‌تنهایی نمی‌گوید دقیقاً کجای مسیر یادگیری اشکال دارد. وقتی هوش مصنوعی دلیل هر پاسخ غلط را توضیح می‌دهد، دانش‌آموز می‌فهمد آیا اشکال از عدم مطالعه بوده، بدفهمی مفهوم یا فقط بی‌دقتی؛ و بر اساس همین بازخورد می‌تواند <a href="/plan">برنامه مطالعاتی‌اش</a> را برای مرور بیشتر همان مبحث تنظیم کند.</p>

<h2>جمع‌بندی</h2>
<p>ترکیب آزمون تستی و تشریحی، همراه با افزایش تدریجی سطح سختی و بررسی دقیق پاسخ‌های غلط، مسیر یادگیری را بسیار مؤثرتر می‌کند. برای دیدن جایگاهت نسبت به سایر دانش‌آموزان هم می‌توانی سری به <a href="/leaderboard">جدول رتبه‌بندی نورتیکا</a> بزنی، یا مقاله <a href="/blog/program-study">برنامه مطالعاتی مؤثر</a> را هم بخوانی.</p>
""",
    },
    "konkur": {
        "title": "برنامه‌ریزی برای کنکور را از همین امروز شروع کن",
        "description": "چرا نباید برنامه‌ریزی کنکور را به سال آخر موکول کرد، نقش وزن‌دهی دروس بر اساس رشته هدف دانشگاهی، و چطور با آزمون‌های دوره‌ای و رقابت سالم آماده‌تر به کنکور برسیم.",
        "category": "کنکور",
        "published": "2026-06-20",
        "modified": "2026-07-01",
        "body_html": """
<p>یکی از رایج‌ترین اشتباهات داوطلبان کنکور، به‌تعویق‌انداختن برنامه‌ریزی جدی تا تابستان پایه دوازدهم است. در حالی که پایه‌های درسی مهم، از همان دهم و یازدهم شکل می‌گیرند و جمع‌بندی فشرده در چند ماه پایانی، جای مطالعه اصولی چندساله را نمی‌گیرد.</p>

<h2>چرا باید از همین امروز شروع کرد؟</h2>
<p>کتاب‌های دهم و یازدهم بخش قابل‌توجهی از سؤالات کنکور را تشکیل می‌دهند، به‌خصوص در دروس تخصصی مثل ریاضی، فیزیک، شیمی و زیست‌شناسی. اگر برنامه‌ریزی از همین پایه‌ها شروع شود، در دوازدهم فقط باید مباحث جدید را همراه با جمع‌بندی سال‌های قبل پیش برد، نه اینکه همه‌چیز را از صفر مرور کرد.</p>

<h2>نقش وزن‌دهی دروس بر اساس رشته هدف دانشگاهی</h2>
<p>یکی از تفاوت‌های اصلی برنامه‌ریزی هوشمند با برنامه‌های عمومی، توجه به رشته هدف دانشگاهی است. برای مثال داوطلب پزشکی باید زمان بیشتری روی زیست‌شناسی و شیمی بگذارد، در حالی که داوطلب مهندسی کامپیوتر باید تمرکز بیشتری روی ریاضی، حسابان و ریاضیات گسسته داشته باشد. در <a href="/plan">صفحه برنامه‌ریزی نورتیکا</a> با واردکردن رشته هدف، همین وزن‌دهی به‌صورت خودکار در برنامه اعمال می‌شود؛ برای آشنایی بیشتر با این فرایند مقاله <a href="/blog/program-study">چگونه یک برنامه مطالعاتی مؤثر بچینیم</a> را هم بخوان.</p>

<h2>نقش آزمون‌های دوره‌ای و رقابت سالم</h2>
<p>جمع‌بندی کنکور بدون سنجش مداوم عملاً کورکورانه پیش می‌رود. با <a href="/exam">آزمون‌های آنلاین دوره‌ای</a> می‌توانی دقیقاً بفهمی کدام فصل‌ها را باید بیشتر مرور کنی. همچنین حضور در <a href="/leaderboard">جدول رتبه‌بندی</a> و دیدن پیشرفت دیگر داوطلبان، انگیزه لازم برای ادامه مسیر طولانی کنکور را حفظ می‌کند.</p>

<h2>جمع‌بندی</h2>
<p>برنامه‌ریزی برای کنکور یک پروژه چندساله است، نه یک اسپرینت چندماهه. هرچه زودتر با یک برنامه اولویت‌بندی‌شده و وزن‌دهی‌شده بر اساس هدفت شروع کنی، در سال آخر با آرامش بیشتری به جمع‌بندی می‌رسی. برای سؤالات بیشتر درباره نحوه استفاده از امکانات نورتیکا هم می‌توانی به <a href="/support">صفحه پشتیبانی</a> سر بزنی.</p>
""",
    },
}


def _article_schema(slug: str, post: dict) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": post["description"],
        "datePublished": post["published"],
        "dateModified": post["modified"],
        "inLanguage": "fa-IR",
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"{SITE_URL}/blog/{slug}"},
        "image": f"{SITE_URL}/logo.jpg",
        "author": {"@type": "Organization", "name": "نورتیکا", "url": SITE_URL or "/"},
        "publisher": {
            "@type": "Organization",
            "name": "نورتیکا",
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/logo.jpg"},
        },
    }
    return _ld_json(data)
def _db_posts(db):
    """مقالاتی که از پنل ادمین (/admin) اضافه شده‌اند (از دیتابیس)."""
    if db is None:
        return []
    return db.query(models.BlogPost).order_by(models.BlogPost.created_at.desc()).all()


def blog_index_page(db=None) -> str:
    cards = []
    for slug, post in BLOG_POSTS.items():
        cards.append(f"""
<a href="/blog/{slug}" class="card" style="display:block;text-decoration:none;color:inherit;">
  <span class="badge-note">{post['category']}</span>
  <h2 style="margin-top:10px;">{post['title']}</h2>
  <p style="color:var(--text-muted);">{post['description']}</p>
</a>""")
    for user_post in _db_posts(db):
        cover_html = (
            f'<img src="{user_post.image_url}" alt="{user_post.title}" loading="lazy" '
            f'style="width:100%;aspect-ratio:16/9;border-radius:12px;margin-bottom:12px;object-fit:cover;max-height:220px;" />'
            if getattr(user_post, "image_url", None) else ""
        )
        cards.append(f"""
<a href="/blog/{user_post.slug}" class="card" style="display:block;text-decoration:none;color:inherit;">
  {cover_html}
  <span class="badge-note">مقاله جدید</span>
  <h2 style="margin-top:10px;">{user_post.title}</h2>
  <p style="color:var(--text-muted);">{user_post.description}</p>
</a>""")
    body = f"""
<div class="hero">
  <h1>وبلاگ نورتیکا</h1>
  <p>مقالات آموزشی درباره برنامه‌ریزی درسی، آزمون آنلاین و آمادگی کنکور برای دانش‌آموزان متوسطه اول و دوم.</p>
</div>
{"".join(cards)}
"""
    blog_schema = _ld_json({
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": "وبلاگ نورتیکا",
        "url": f"{SITE_URL}/blog",
        "blogPost": [
            {
                "@type": "BlogPosting",
                "headline": post["title"],
                "url": f"{SITE_URL}/blog/{slug}",
                "datePublished": post["published"],
            }
            for slug, post in BLOG_POSTS.items()
        ],
    })
    return base_page(
        "وبلاگ نورتیکا | مقالات برنامه‌ریزی درسی، آزمون و کنکور",
        "/blog", body,
        meta_description="مقالات آموزشی نورتیکا درباره برنامه‌ریزی درسی، آزمون آنلاین و آمادگی کنکور برای دانش‌آموزان متوسطه اول و دوم.",
        extra_schema=blog_schema,
        breadcrumb_items=[("خانه", "/"), ("وبلاگ", "/blog")],
    )


def blog_post_page(slug: str, db=None):
    post = BLOG_POSTS.get(slug)
    if post:
        body = f"""
<article class="card">
  <span class="badge-note">{post['category']}</span>
  <h1 style="margin-top:10px;">{post['title']}</h1>
  {post['body_html']}
</article>
"""
        return base_page(
            f"{post['title']} | وبلاگ نورتیکا",
            f"/blog/{slug}", body,
            meta_description=post["description"],
            extra_schema=_article_schema(slug, post),
            breadcrumb_items=[("خانه", "/"), ("وبلاگ", "/blog"), (post["title"], f"/blog/{slug}")],
            og_image=post.get("image_url", ""),
        )

    user_post = None
    if db is not None:
        user_post = db.query(models.BlogPost).filter(models.BlogPost.slug == slug).first()
    if not user_post:
        return None

    cover_html = (
        f'<img src="{user_post.image_url}" alt="{user_post.title}" loading="eager" fetchpriority="high" '
        f'style="width:100%;aspect-ratio:16/9;border-radius:14px;margin-bottom:16px;object-fit:cover;max-height:360px;" />'
        if getattr(user_post, "image_url", None) else ""
    )
    link_html = (
        f'<p style="margin-top:16px;"><a href="{user_post.link_url}" target="_blank" rel="noopener" '
        f'class="btn secondary">مشاهده لینک مرتبط</a></p>'
        if getattr(user_post, "link_url", None) else ""
    )
    body = f"""
<article class="card">
  {cover_html}
  <span class="badge-note">مقاله جدید</span>
  <h1 style="margin-top:10px;">{user_post.title}</h1>
  <p>{user_post.description}</p>
  {link_html}
</article>
"""
    published_iso = user_post.created_at.strftime("%Y-%m-%dT%H:%M:%S+03:30") if getattr(user_post, "created_at", None) else ""
    user_article_schema = _ld_json({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": user_post.title,
        "description": user_post.description[:150],
        "datePublished": published_iso,
        "dateModified": published_iso,
        "inLanguage": "fa-IR",
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"{SITE_URL}/blog/{slug}"},
        "image": user_post.image_url if getattr(user_post, "image_url", None) else f"{SITE_URL}/logo.jpg",
        "author": {"@type": "Organization", "name": "نورتیکا", "url": SITE_URL or "/"},
        "publisher": {
            "@type": "Organization",
            "name": "نورتیکا",
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/logo.jpg"},
        },
    })
    return base_page(
        f"{user_post.title} | وبلاگ نورتیکا",
        f"/blog/{slug}", body,
        meta_description=user_post.description[:150],
        extra_schema=user_article_schema,
        breadcrumb_items=[("خانه", "/"), ("وبلاگ", "/blog"), (user_post.title, f"/blog/{slug}")],
        og_image=user_post.image_url or "",
    )
