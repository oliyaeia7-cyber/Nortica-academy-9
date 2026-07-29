"""
redirect_manager.py
====================

سیستم مرکزی و سازمانی (Enterprise) مدیریت Redirectهای HTTP برای نورتیکا.

هدف
----
یک منبع حقیقت واحد (Single Source of Truth) برای همه‌ی Redirectهای سایت،
مستقل از منطق صفحات (pages.py) و روترهای API، طوری که:

  • افزودن/حذف Redirect جدید فقط با اضافه/حذف یک خط در REDIRECT_RULES باشد.
  • هیچ Redirect Loop یا Redirect Chain در زمان بالا آمدن سرویس (startup) اجازه
    ثبت پیدا نکند (Fail Fast — قبل از رسیدن ترافیک واقعی خطا داده می‌شود).
  • هیچ Open Redirect (ریدایرکت به دامنه‌ی دلخواه/غیرمجاز) ممکن نباشد.
  • جست‌وجوی هر Redirect در زمان ثابت O(1) انجام شود (dict lookup)، حتی با
    هزاران قانون، تا هیچ افت سرعتی روی مسیرهای عادی سایت ایجاد نشود.
  • سازگار با robots.txt / sitemap.xml / canonical باشد: مسیرهای رزرو شده‌ی
    سیستم (مثل خود robots.txt، sitemap.xml، صفحات اصلی و استاتیک‌ها) هرگز
    توسط یک Redirect بازنویسی نمی‌شوند تا موتورهای جست‌وجو و Google Search
    Console سردرگم نشوند.

معماری (SOLID)
---------------
  • RedirectRule            -> فقط نگه‌دارنده‌ی داده‌ی یک قانون (SRP).
  • RedirectValidationError -> خطای اختصاصی برای شکست اعتبارسنجی.
  • RedirectManager         -> مسئول ثبت، اعتبارسنجی و جست‌وجوی قوانین (SRP).
  • RedirectMiddleware      -> فقط مسئول اتصال RedirectManager به FastAPI/ASGI
                               است؛ هیچ منطق کسب‌وکاری در آن نیست (SRP + DIP:
                               به انتزاع RedirectManager وابسته است، نه به
                               جزئیات پیاده‌سازی).

این جداسازی باعث می‌شود بتوان بعداً منبع Redirectها را بدون تغییر middleware
از یک لیست پایتونی به دیتابیس/فایل JSON/Redis منتقل کرد (Open/Closed Principle).

نحوه‌ی اتصال به main.py
------------------------
فقط دو خط باید در main.py اضافه شود (چیز دیگری تغییر نمی‌کند):

    from redirect_manager import RedirectMiddleware, redirect_manager
    app.add_middleware(RedirectMiddleware, manager=redirect_manager)

میدلور باید *قبل* از CORSMiddleware و پیش از رسیدن به روتینگ FastAPI اجرا شود
تا حتی برای مسیرهایی که دیگر route ندارند (صفحات/APIهای حذف‌شده) هم درست کار
کند و ۴۰۴ اشتباه به گوگل نده.

افزودن یک Redirect جدید در آینده
----------------------------------
کافی است یک خط به لیست REDIRECT_RULES در پایین همین فایل اضافه شود:

    RedirectRule(
        source="/masir-ghadim",          # مسیر قدیمی (باید با / شروع شود)
        target="/plan",                  # مسیر جدید یا URL کامل مجاز
        status_code=301,                 # 301 دائمی یا 302 موقت
        note="ادغام صفحه‌ی مسیر با صفحه‌ی برنامه‌ریزی",
    ),

سرویس در زمان استارت‌آپ به‌صورت خودکار قانون جدید را اعتبارسنجی می‌کند
(حلقه، زنجیره، مسیر رزرو شده، Open Redirect) و در صورت مشکل با خطای واضح
از بالا آمدن جلوگیری می‌کند تا باگ به Production نرسد.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp


# --------------------------------------------------------------------------- #
# پیکربندی امنیتی: جلوگیری از Open Redirect
# --------------------------------------------------------------------------- #
# فقط ریدایرکت به مسیرهای داخلی (شروع با "/") یا دامنه‌های داخل این لیست
# سفید (Whitelist) مجاز است. به‌صورت پیش‌فرض هیچ دامنه‌ی خارجی مجاز نیست؛ در
# صورت نیاز واقعی، دامنه را از طریق متغیر محیطی زیر اضافه کن (کاما جدا از هم):
#   ALLOWED_REDIRECT_HOSTS="noortika.com,www.noortika.com"
_ALLOWED_EXTERNAL_HOSTS: frozenset[str] = frozenset(
    h.strip().lower()
    for h in os.environ.get("ALLOWED_REDIRECT_HOSTS", "").split(",")
    if h.strip()
)

# مسیرهایی که هسته‌ی سئو/سیستم به آن‌ها وابسته است و هرگز نباید override شوند
# (خودِ فایل‌های robots/sitemap، سلامت سرویس، فایل‌های استاتیک و منابع لوگو).
# این‌ها با پیشوند هم بررسی می‌شوند تا کل زیرمسیر /static/ محافظت شود.
RESERVED_EXACT_PATHS: frozenset[str] = frozenset(
    {"/robots.txt", "/sitemap.xml", "/health", "/logo.jpg"}
)
RESERVED_PATH_PREFIXES: tuple[str, ...] = ("/static/",)


class RedirectValidationError(Exception):
    """در صورت نامعتبر بودن یک قانون Redirect (حلقه، زنجیره، مسیر رزرو‌شده،
    یا هدف غیرمجاز) در زمان ثبت (startup) پرتاب می‌شود."""


@dataclass(frozen=True, slots=True)
class RedirectRule:
    """
    نگه‌دارنده‌ی داده‌ی یک قانون Redirect (بدون منطق — فقط داده، طبق SRP).

    Attributes:
        source: مسیر قدیمی که باید ریدایرکت شود؛ همیشه با "/" شروع می‌شود و
            بدون query string (مثلاً "/blog/old-slug").
        target: مقصد ریدایرکت. یا یک مسیر داخلی با "/" (توصیه‌شده) یا یک
            URL کامل به دامنه‌ای که در ALLOWED_REDIRECT_HOSTS سفید شده باشد.
        status_code: 301 (دائمی، حافظ Link Equity برای سئو) یا 302 (موقت).
        preserve_query: اگر True باشد، query string درخواست ورودی به انتهای
            مقصد اضافه می‌شود (مفید برای کمپین‌ها/UTM هنگام ریدایرکت موقت).
        active: اگر False باشد، قانون بدون حذف از لیست، غیرفعال می‌شود
            (مفید برای خاموش/روشن سریع بدون از دست دادن تاریخچه در دیف/گیت).
        note: توضیح انسانی برای مستندسازی (چرا این ریدایرکت وجود دارد).
    """

    source: str
    target: str
    status_code: int = 301
    preserve_query: bool = False
    active: bool = True
    note: str = ""

    def __post_init__(self) -> None:
        if self.status_code not in (301, 302):
            raise RedirectValidationError(
                f"status_code نامعتبر برای '{self.source}': فقط 301 یا 302 مجاز است."
            )
        if not self.source.startswith("/"):
            raise RedirectValidationError(
                f"source باید با '/' شروع شود: '{self.source}'"
            )
        if "?" in self.source or "#" in self.source:
            raise RedirectValidationError(
                f"source نباید شامل query/fragment باشد: '{self.source}'"
            )
        if not self.target:
            raise RedirectValidationError(f"target نمی‌تواند خالی باشد برای '{self.source}'")


class RedirectManager:
    """
    مدیر مرکزی Redirectها.

    مسئولیت‌ها (SRP):
      1) اعتبارسنجی مجموعه‌ی قوانین در لحظه‌ی ساخت (جلوگیری از Loop/Chain/
         Open Redirect/تداخل با مسیرهای رزرو‌شده).
      2) جست‌وجوی O(1) یک مسیر ورودی و برگرداندن قانون منطبق (در صورت وجود).

    طراحی برای مقیاس: تمام قوانینِ فعال داخل یک dict نگه‌داری می‌شوند، بنابراین
    حتی با هزاران Redirect، زمان جست‌وجو مستقل از تعداد قوانین و ثابت است.
    """

    def __init__(self, rules: Iterable[RedirectRule]) -> None:
        self._rules_by_source: dict[str, RedirectRule] = {}
        for rule in rules:
            if not rule.active:
                continue
            if rule.source in self._rules_by_source:
                raise RedirectValidationError(
                    f"تعریف تکراری برای مسیر '{rule.source}' — هر مسیر فقط یک قانون می‌تواند داشته باشد."
                )
            self._rules_by_source[rule.source] = rule

        self._validate_no_reserved_conflicts()
        self._validate_no_self_loop()
        self._validate_no_redirect_chain()
        self._validate_no_open_redirect()

    # --------------------------- اعتبارسنجی‌ها --------------------------- #

    def _validate_no_reserved_conflicts(self) -> None:
        """جلوگیری از override شدن مسیرهای حیاتی سئو/سیستم توسط یک Redirect."""
        for source in self._rules_by_source:
            if source in RESERVED_EXACT_PATHS or source.startswith(RESERVED_PATH_PREFIXES):
                raise RedirectValidationError(
                    f"مسیر '{source}' رزرو‌شده‌ی سیستم است و نمی‌تواند Redirect داشته باشد "
                    "(robots.txt/sitemap.xml/health/static در تضاد قرار می‌گیرند)."
                )

    def _validate_no_self_loop(self) -> None:
        """جلوگیری از Redirect Loop مستقیم: source == target."""
        for rule in self._rules_by_source.values():
            if self._normalize(rule.target) == self._normalize(rule.source):
                raise RedirectValidationError(
                    f"Redirect Loop شناسایی شد: '{rule.source}' به خودش اشاره می‌کند."
                )

    def _validate_no_redirect_chain(self) -> None:
        """
        جلوگیری از Redirect Chain: اگر مقصدِ یک قانون، خودش مبدأِ یک قانون
        دیگر باشد (A -> B و B -> C)، این برای سئو ضعیف است (اتلاف Link Equity
        و کندی برای کراولر) و هم می‌تواند به یک حلقه‌ی غیرمستقیم منجر شود.
        این‌جا به‌صورت سخت‌گیرانه هر زنجیره‌ای را رد می‌کنیم؛ راه‌حل درست همیشه
        این است که خودِ قانون A مستقیماً به C اشاره کند.
        """
        for rule in self._rules_by_source.values():
            target_path = self._internal_path_of(rule.target)
            if target_path is not None and target_path in self._rules_by_source:
                raise RedirectValidationError(
                    f"Redirect Chain شناسایی شد: '{rule.source}' -> '{rule.target}' "
                    f"-> ... . مقصد '{rule.target}' خودش مبدأ یک Redirect دیگر است؛ "
                    "به‌جای زنجیره، مستقیماً به مقصد نهایی اشاره کن."
                )

    def _validate_no_open_redirect(self) -> None:
        """
        جلوگیری از Open Redirect: مقصد باید یا مسیر داخلی نسبی باشد، یا یک
        URL کامل با دامنه‌ای که صراحتاً در ALLOWED_REDIRECT_HOSTS سفید شده.
        همچنین از الگوهای رایج دور زدنِ اعتبارسنجی (protocol-relative مثل
        "//evil.com" یا اسکیم‌های غیر http/https) جلوگیری می‌شود.
        """
        for rule in self._rules_by_source.values():
            target = rule.target

            # protocol-relative URL مثل "//evil.com" یک ترفند رایج Open Redirect است.
            if target.startswith("//"):
                raise RedirectValidationError(
                    f"مقصد غیرمجاز (protocol-relative) در '{rule.source}': '{target}'"
                )

            if target.startswith("/"):
                continue  # مسیر داخلی نسبی -> همیشه امن.

            parsed = urlparse(target)
            if parsed.scheme not in ("http", "https"):
                raise RedirectValidationError(
                    f"اسکیم غیرمجاز در مقصد '{rule.source}': '{target}'"
                )
            host = (parsed.hostname or "").lower()
            if host not in _ALLOWED_EXTERNAL_HOSTS:
                raise RedirectValidationError(
                    f"Open Redirect بالقوه: دامنه‌ی مقصد '{host}' برای مسیر "
                    f"'{rule.source}' در ALLOWED_REDIRECT_HOSTS سفید نشده است."
                )

    # ------------------------------ ابزارها ------------------------------ #

    @staticmethod
    def _normalize(path: str) -> str:
        """مسیر را برای مقایسه یکسان‌سازی می‌کند (بدون اسلش انتهایی اضافه)."""
        if len(path) > 1 and path.endswith("/"):
            return path[:-1]
        return path

    @staticmethod
    def _internal_path_of(target: str) -> Optional[str]:
        """اگر target یک مسیر داخلی باشد مسیر را برمی‌گرداند، وگرنه None."""
        if target.startswith("/") and not target.startswith("//"):
            return RedirectManager._normalize(target)
        return None

    # ------------------------------- API عمومی ------------------------------ #

    def resolve(self, path: str) -> Optional[RedirectRule]:
        """جست‌وجوی O(1) قانون منطبق با مسیر ورودی؛ در نبود تطبیق None."""
        return self._rules_by_source.get(self._normalize(path))

    def __len__(self) -> int:
        return len(self._rules_by_source)


class RedirectMiddleware(BaseHTTPMiddleware):
    """
    میدلور ASGI که RedirectManager را به FastAPI متصل می‌کند.

    این میدلور *پیش از* روتینگ FastAPI اجرا می‌شود، بنابراین حتی برای
    مسیرهایی که دیگر route فعالی ندارند (صفحه/API حذف‌شده) هم درست کار
    می‌کند و به‌جای ۴۰۴، ریدایرکت صحیح (301/302) برمی‌گرداند — دقیقاً همان
    چیزی که Google Search Console برای سلامت ایندکس انتظار دارد.

    عملکرد: هر درخواست فقط یک dict lookup اضافه می‌کند (O(1))، پس حتی با
    هزاران قانون، تأثیر محسوسی روی زمان پاسخ مسیرهای عادی سایت ندارد.
    """

    def __init__(self, app: ASGIApp, manager: RedirectManager) -> None:
        super().__init__(app)
        self._manager = manager

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rule = self._manager.resolve(request.url.path)
        if rule is None:
            return await call_next(request)

        location = rule.target
        if rule.preserve_query and request.url.query:
            separator = "&" if "?" in location else "?"
            location = f"{location}{separator}{request.url.query}"

        return RedirectResponse(url=location, status_code=rule.status_code)


# --------------------------------------------------------------------------- #
# ثبت قوانین Redirect — تنها جایی که برای افزودن/حذف Redirect باید ویرایش شود
# --------------------------------------------------------------------------- #
#
# نکات سئو مهم هنگام افزودن قانون جدید:
#   • برای ادغام دائمی/جابه‌جایی همیشگی صفحه از 301 استفاده کن (Link Equity
#     حفظ می‌شود و گوگل ایندکس قدیمی را به مقصد جدید منتقل می‌کند).
#   • برای رویدادها/کمپین‌های موقت یا A/B test از 302 استفاده کن (گوگل صفحه‌ی
#     مبدأ را در ایندکس نگه می‌دارد چون قرار است بعداً برگردد).
#   • همیشه به مقصد *نهایی* اشاره کن، نه به یک Redirect دیگر (از Chain جلوگیری
#     می‌شود؛ در غیر این صورت RedirectManager در استارت‌آپ خطا می‌دهد).
#   • بعد از افزودن یک 301 جدید برای صفحه‌ای که در sitemap.xml (main.py) بود،
#     مسیر قدیمی را از لیست paths در main.py حذف کن تا سایت‌مپ فقط شامل
#     URLهای نهایی/canonical باشد.
#
REDIRECT_RULES: list[RedirectRule] = [
    # نمونه‌ی 301 (دائمی): تغییر نام یک مسیر قدیمی برنامه‌ریزی به مسیر جدید.
    # RedirectRule(
    #     source="/planner",
    #     target="/plan",
    #     status_code=301,
    #     note="یکسان‌سازی نام‌گذاری مسیر برنامه‌ریزی تحصیلی",
    # ),
    #
    # نمونه‌ی 302 (موقت): ریدایرکت موقت صفحه‌ی اصلی به یک لندینگ کمپین.
    # RedirectRule(
    #     source="/campaign",
    #     target="/pricing",
    #     status_code=302,
    #     preserve_query=True,
    #     note="کمپین تبلیغاتی موقت مردادماه — بعد از پایان کمپین حذف شود",
    # ),
]

# نمونه‌ی singleton آماده‌ی استفاده در main.py.
redirect_manager = RedirectManager(REDIRECT_RULES)
