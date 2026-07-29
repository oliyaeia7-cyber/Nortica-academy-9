from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, Response, PlainTextResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
import base64

from database import Base, engine, get_db, SessionLocal
import models  # noqa: F401  -> ثبت مدل‌ها روی Base
from assets import LOGO_DATA_URI, BRAIN_DATA_URI, TELEGRAM_ICON_DATA_URI, INSTAGRAM_ICON_DATA_URI, BALE_ICON_DATA_URI, GMAIL_ICON_DATA_URI

import users_router
import plans_router
import chat_planner_router
import study_router
import exams_router
import leaderboard_router
import support_router
import subscription_router
import blog_router
import admin_router
import media_router
import links_router
import admin_data_router
import question_bank_router
import consultation_router
import major_selection_router

import pages

from redirect_manager import RedirectMiddleware, redirect_manager

Base.metadata.create_all(bind=engine)

from question_bank_seed import seed_question_bank
from subscription_router import seed_pricing_plans
_seed_db = SessionLocal()
try:
    seed_question_bank(_seed_db, models)
    seed_pricing_plans(_seed_db)
finally:
    _seed_db.close()

app = FastAPI(title="نورتیکا | Noortika")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def security_and_canonical_host_middleware(request: Request, call_next):
    # --- ریدایرکت به https و حذف www (اگر SITE_URL روی Render ست شده باشد) ---
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", "")
    site_url = pages.SITE_URL or ""

    if site_url:
        canonical_host = site_url.split("://", 1)[-1].split("/", 1)[0]
        needs_https = forwarded_proto == "http"
        needs_host_fix = host and host != canonical_host and host == f"www.{canonical_host}"
        if needs_https or needs_host_fix:
            target = f"https://{canonical_host}{request.url.path}"
            if request.url.query:
                target += f"?{request.url.query}"
            return RedirectResponse(url=target, status_code=301)

    response = await call_next(request)

    # --- هدرهای امنیتی روی همه‌ی پاسخ‌ها ---
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if forwarded_proto == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return HTMLResponse(content=pages.not_found_page(), status_code=404)
    if exc.status_code == 500:
        return HTMLResponse(content=pages.server_error_page(), status_code=500)
    return HTMLResponse(
        content=f"<h1 style='font-family:sans-serif;text-align:center;margin-top:80px;'>{exc.detail}</h1>",
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def custom_unhandled_exception_handler(request: Request, exc: Exception):
    return HTMLResponse(content=pages.server_error_page(), status_code=500)

# میدلور Redirect باید بعد از CORS اضافه شود تا در استک ASGI بیرونی‌تر باشد
# و پیش از رسیدن درخواست به روتینگ FastAPI اجرا شود (حتی برای مسیرهای
# حذف‌شده‌ای که دیگر route فعالی ندارند). جزئیات کامل و نحوه‌ی افزودن
# Redirect جدید در redirect_manager.py مستند شده است.
app.add_middleware(RedirectMiddleware, manager=redirect_manager)

app.include_router(users_router.router)
app.include_router(plans_router.router)
app.include_router(chat_planner_router.router)
app.include_router(study_router.router)
app.include_router(exams_router.router)
app.include_router(leaderboard_router.router)
app.include_router(support_router.router)
app.include_router(subscription_router.router)
app.include_router(blog_router.router)
app.include_router(admin_router.router)
app.include_router(media_router.router)
app.include_router(links_router.router)
app.include_router(admin_data_router.router)
app.include_router(question_bank_router.router)
app.include_router(consultation_router.router)
app.include_router(major_selection_router.router)

_LOGO_BYTES = base64.b64decode(LOGO_DATA_URI.split(",", 1)[1])
_BRAIN_BYTES = base64.b64decode(BRAIN_DATA_URI.split(",", 1)[1])
_TELEGRAM_ICON_BYTES = base64.b64decode(TELEGRAM_ICON_DATA_URI.split(",", 1)[1])
_INSTAGRAM_ICON_BYTES = base64.b64decode(INSTAGRAM_ICON_DATA_URI.split(",", 1)[1])
_BALE_ICON_BYTES = base64.b64decode(BALE_ICON_DATA_URI.split(",", 1)[1])
_GMAIL_ICON_BYTES = base64.b64decode(GMAIL_ICON_DATA_URI.split(",", 1)[1])


@app.get("/icons/gmail.png")
def serve_gmail_icon():
    return Response(
        content=_GMAIL_ICON_BYTES,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/icons/telegram.png")
def serve_telegram_icon():
    return Response(
        content=_TELEGRAM_ICON_BYTES,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/icons/instagram.png")
def serve_instagram_icon():
    return Response(
        content=_INSTAGRAM_ICON_BYTES,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/icons/bale.png")
def serve_bale_icon():
    return Response(
        content=_BALE_ICON_BYTES,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/logo.jpg")
def serve_logo():
    return Response(
        content=_LOGO_BYTES,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=2592000"},
    )


@app.get("/brain.png")
def serve_brain():
    return Response(
        content=_BRAIN_BYTES,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=2592000"},
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    site = pages.SITE_URL or ""
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        "Disallow: /404\n"
        "Disallow: /500\n\n"
        f"Sitemap: {site}/sitemap.xml\n"
    )


@app.get("/sitemap.xml")
def sitemap_xml():
    site = pages.SITE_URL or ""
    paths = ["/", "/plan", "/exam", "/consultation", "/major-selection", "/leaderboard", "/pricing", "/support", "/blog"]
    paths += [f"/blog/{slug}" for slug in pages.BLOG_POSTS.keys()]
    urls = "\n".join(
        f"  <url><loc>{site}{p}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>"
        for p in paths
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/static/style.css")
def static_style_css():
    return Response(
        content=pages.CSS_TEXT,
        media_type="text/css",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/static/theme.js")
def static_theme_js():
    return Response(
        content=pages.THEME_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/static/bg3d.js")
def static_bg3d_js():
    return Response(
        content=pages.BG3D_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/", response_class=HTMLResponse)
def home(db: Session = Depends(get_db)):
    return pages.index_page(db)


@app.get("/plan", response_class=HTMLResponse)
def plan_page():
    return pages.plan_page()


@app.get("/exam", response_class=HTMLResponse)
def exam_page():
    return pages.exam_page()


@app.get("/consultation", response_class=HTMLResponse)
def consultation_page():
    return pages.consultation_page()


@app.get("/major-selection", response_class=HTMLResponse)
def major_selection_page():
    return pages.major_selection_page()


@app.get("/leaderboard", response_class=HTMLResponse)
def leaderboard_page():
    return pages.leaderboard_page()


@app.get("/pricing", response_class=HTMLResponse)
def pricing_page():
    return pages.pricing_page()


@app.get("/support", response_class=HTMLResponse)
def support_page():
    return pages.support_page()


@app.get("/blog", response_class=HTMLResponse)
def blog_index(db: Session = Depends(get_db)):
    return pages.blog_index_page(db)


@app.get("/blog/{slug}", response_class=HTMLResponse)
def blog_post(slug: str, db: Session = Depends(get_db)):
    html = pages.blog_post_page(slug, db)
    if html is None:
        return HTMLResponse(
            content="<h1 style='font-family:sans-serif;text-align:center;margin-top:80px;'>مقاله مورد نظر پیدا نشد.</h1>"
                    "<p style='text-align:center;'><a href='/blog'>بازگشت به وبلاگ</a></p>",
            status_code=404,
        )
    return HTMLResponse(content=html)
