# پلن: فعال‌سازی کامل آپشن‌های بات (سهمیه حجمی + زبان + منوها + ارورهای بهتر + پنل ادمین)

## Summary
- اضافه کردن سهمیه مصرف حجمی روزانه برای کاربران (رایگان ۱۰GB / پرمیوم ۵۰GB) با ریست نیمه‌شب تهران
- انتخاب زبان (فارسی/انگلیسی) در اولین /start (رفتار فعلی حفظ و کامل‌تر می‌شود)
- پیاده‌سازی تمام گزینه‌های منوی اصلی بات (Your Files / Inline Search / Contact / Rules / Services / Referral / Premium / News)
- بهبود پیام‌های خطا برای کاربر (نمایش دلیل قابل فهم، بدون نمایش ارورهای سیستمی)
- افزودن قابلیت ادمین برای مشاهده لیست کاربران و مشاهده تاریخچه لینک‌های دانلود هر کاربر

## Current State Analysis (بر اساس ریپوی فعلی)
- بات با aiogram v3 ساخته شده و روترها در [main.py](file:///Users/petty/p/01downloader/bot/main.py#L13-L43) رجیستر می‌شوند: admin/start/download
- دیتابیس SQLite در [database.py](file:///Users/petty/p/01downloader/bot/models/database.py) شامل جدول‌های users/downloads/pending_downloads است
- انتخاب زبان در /start تا حدی پیاده شده (ستون language_selected) و اگر انتخاب نشده باشد، منوی زبان نمایش داده می‌شود: [start.py](file:///Users/petty/p/01downloader/bot/handlers/start.py#L12-L28)
- منوی اصلی دکمه‌های زیادی دارد اما اکثر callbackها هنوز “coming soon” هستند: [start.py](file:///Users/petty/p/01downloader/bot/handlers/start.py#L55-L79)
- محدودیت فعلی صرفاً تعداد دانلود در ۲۴ ساعت است (daily_limit) و حجم مصرفی وجود ندارد: [database.py](file:///Users/petty/p/01downloader/bot/models/database.py#L77-L85)
- خطاها غالباً به صورت رشته خام (str(e)) به کاربر نمایش داده می‌شوند: [download.py](file:///Users/petty/p/01downloader/bot/handlers/download.py#L843-L846)
- پنل ادمین فعلی فقط آمار کلی و /logs و /db دارد: [admin.py](file:///Users/petty/p/01downloader/bot/handlers/admin.py)

## Assumptions & Decisions (قفل‌شده با پاسخ‌های شما)
- ریست سهمیه حجمی: نیمه‌شب تهران
- پلن‌ها: رایگان + پرمیوم
- Referral: پاداش افزایش سقف روزانه (bonus روزانه) برای دعوت‌کننده
- نمایش تاریخچه دانلود در پنل ادمین: URL کامل
- Contact: نمایش لینک/یوزرنیم کانال @sefroyeki (به صورت t.me/sefroyeki)
- سقف پرمیوم: ۵۰GB در روز
- مدیریت پرمیوم: هم از config (لیست PREMIUM_IDS) و هم با دستور ادمین (در دیتابیس)

## Proposed Changes

### 1) تنظیمات جدید (Config)
**فایل:** [settings.py](file:///Users/petty/p/01downloader/bot/config/settings.py)
- اضافه کردن تنظیمات زیر (با مقدار پیش‌فرض):
  - `free_daily_quota_gb: int = 10`
  - `premium_daily_quota_gb: int = 50`
  - `referral_bonus_gb: int = 1` (به ازای هر دعوت موفق، افزایش سقف روزانه دعوت‌کننده)
  - `premium_ids: List[int] = []` (برای حالت “هر دو”، این لیست هم پشتیبانی می‌شود)
  - `support_channel: str = "https://t.me/sefroyeki"`
  - `quota_timezone: str = "Asia/Tehran"` (صرفاً برای شفافیت/آینده؛ منطق ریست با “تاریخ تهران” محاسبه می‌شود)

### 2) تغییرات دیتابیس (Schema + API)
**فایل:** [database.py](file:///Users/petty/p/01downloader/bot/models/database.py)

#### 2.1) Schema migrations
- افزودن ستون‌های جدید به `users` با الگوی فعلیِ migration (PRAGMA table_info + ALTER TABLE):
  - `is_premium INTEGER DEFAULT 0`
  - `referral_bonus_gb INTEGER DEFAULT 0`
  - `referred_by INTEGER NULL` (برای ثبت referrer)
- افزودن جدول‌های جدید:
  - `daily_usage (user_id INTEGER, ymd TEXT, bytes_used INTEGER, PRIMARY KEY(user_id, ymd))`
  - `referrals (referrer_id INTEGER, referred_id INTEGER UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`
- ارتقای جدول `downloads` برای ثبت جزئیات مورد نیاز منو/ادمین/سهمیه:
  - ستون `bytes INTEGER DEFAULT 0`
  - ستون `title TEXT DEFAULT ''`

#### 2.2) توابع/کوئری‌های جدید
- `get_tehran_ymd() -> str` (خروجی مثل 2026-04-20) برای کل بات به عنوان “کلید روز”
- `get_user_daily_quota_bytes(user_id) -> int`:
  - base quota از config: free یا premium
  - اعمال bonus از `users.referral_bonus_gb`
  - اگر user در `config.premium_ids` باشد، پرمیوم محسوب شود
- `get_user_used_bytes_today(user_id) -> int`
- `can_consume(user_id, bytes_needed) -> tuple[bool, used, limit]`
- `consume_bytes(user_id, bytes_used)` فقط بعد از ارسال موفق فایل به کاربر
- `list_users(limit, offset)` برای ادمین
- `get_user_downloads(user_id, limit, offset)` برای Your Files و پنل ادمین
- `set_user_premium(user_id, is_premium: bool)` و `get_user_premium(user_id)`
- `apply_referral_if_new_user(new_user_id, referrer_id)`:
  - فقط اگر کاربر تازه ثبت‌نام کرده و قبلاً referred نشده
  - insert در referrals (با UNIQUE روی referred_id برای جلوگیری از دوباره‌شماری)
  - افزایش `referral_bonus_gb` برای referrer (مثلاً +1 مطابق config)

### 3) سهمیه حجمی در جریان دانلود
**فایل:** [download.py](file:///Users/petty/p/01downloader/bot/handlers/download.py)
- جایگزین/تکمیل چک فعلی `check_rate_limit` با چک سهمیه حجمی:
  - قبل از دانلود (اگر بتوانیم تخمین بزنیم): نمایش خطای “حجم کافی نیست” و جلوگیری از شروع دانلود
  - بعد از دانلود و قبل از ارسال: اگر اندازه واقعی فایل/فایل‌ها از باقی‌مانده بیشتر بود، ارسال انجام نشود و فایل‌ها پاک شوند
  - بعد از ارسال موفق: ثبت مصرف در `daily_usage` و ثبت `bytes/title` در `downloads`
- محاسبه حجم واقعی:
  - دانلودهای yt-dlp: `os.path.getsize(file_path)`
  - quick_download و Spotify: جمع اندازه تمام `file_paths`
- پیام‌های کاربر:
  - نمایش “باقی‌مانده امروز: XGB” در Stats و هنگام رد شدن

### 4) خطاهای کاربرپسند (بدون ارور سیستمی)
**فایل جدید:** `bot/utils/error_messages.py`
- تابع `to_user_friendly_error(lang: str, err: str) -> str` با rule-based mapping (substring match)
  - نمونه دسته‌ها:
    - لینک پشتیبانی نمی‌شود
    - محتوای خصوصی/نیازمند لاگین
    - بلاک/anti-bot یوتیوب (cookies لازم)
    - geo-block / محدودیت منطقه‌ای
    - تایم‌اوت دانلود/پردازش
    - فایل خیلی بزرگ برای ارسال تلگرام (>2GB)
    - مشکل شبکه/سرور موقت
- در همه مسیرها:
  - log داخلی با logger.exception / logger.error حفظ شود
  - پیام نهایی کاربر از این تابع بیاید، نه `str(e)`

### 5) فعال‌سازی تمام گزینه‌های منوی اصلی
**فایل:** [start.py](file:///Users/petty/p/01downloader/bot/handlers/start.py) + (در صورت نیاز) فایل‌های جدید handler

#### 5.1) Your Files
- `menu_files`: نمایش تاریخچه آخرین دانلودهای همان کاربر (URL + type + تاریخ + حجم)
- pagination با InlineKeyboard (Next/Prev) تا چت شلوغ نشود

#### 5.2) Inline Search
- اضافه کردن inline_query handler (در Router مناسب، مثلاً روتر start یا یک فایل جدید `handlers/inline_search.py`)
- جستجو در history خود کاربر (table downloads) بر اساس query:
  - `url LIKE %query%` یا اگر query خالی بود آخرین موارد
- خروجی inline results از نوع Article (عنوان: domain یا title، متن: URL کامل + نوع/تاریخ)

#### 5.3) Contact Us
- `menu_contact`: نمایش لینک کانال `https://t.me/sefroyeki`

#### 5.4) How to / Rules / Services
- `menu_rules`: توضیح قوانین (سقف حجم روزانه، سقف تلگرام، پیشنهاد انتخاب کیفیت پایین‌تر، …)
- `menu_services`: لیست سرویس‌های پشتیبانی‌شده (مطابق help متن فعلی)
- دکمه “How to use this bot” فعلاً URL دارد؛ متن/URL را در صورت نیاز به کانال/راهنما تغییر می‌دهیم

#### 5.5) Referral Program (با پاداش حجم روزانه)
- `menu_referral`: نمایش لینک دعوت اختصاصی کاربر
- نمایش تعداد دعوت‌های موفق + مقدار bonus فعلی
- تغییر /start برای پشتیبانی از start parameter:
  - `/start <referrer_id>` یا `/start ref_<id>` (هر دو پشتیبانی می‌شوند)
  - فقط روی ثبت‌نام اول اعمال شود

#### 5.6) Premium Subscription
- `menu_premium`: نمایش توضیح پرمیوم + سقف ۵۰GB و راه ارتباط (کانال/ادمین)
- اضافه شدن دستورات ادمین:
  - `/setpremium <user_id>`
  - `/unsetpremium <user_id>`
  - `/premium <user_id>` (اختیاری برای مشاهده وضعیت)

#### 5.7) News & Updates
- `menu_news`: نمایش آخرین پیام خبری (ابتدا از متن ثابت داخل locales)
- آماده‌سازی برای آینده: امکان ذخیره “آخرین خبر” در config یا یک جدول `news` (فعلاً لازم نیست مگر شما بخواهید دینامیک شود)

### 6) پنل ادمین: لیست کاربران + تاریخچه لینک‌ها
**فایل:** [admin.py](file:///Users/petty/p/01downloader/bot/handlers/admin.py)
- افزودن command و callbackها:
  - `/users` → نمایش لیست صفحه‌بندی‌شده کاربران (username یا user_id)
  - انتخاب یک کاربر → نمایش آخرین N دانلود (URL کامل + type + تاریخ + حجم)
  - دکمه “Back” برای برگشت به لیست
- استفاده از توابع جدید دیتابیس (`list_users`, `get_user_downloads`)

### 7) متن‌ها و Locale
**فایل:** [locales.py](file:///Users/petty/p/01downloader/bot/utils/locales.py)
- افزودن keyهای جدید (fa/en):
  - quota: `quota_exceeded`, `quota_status`, `quota_remaining`
  - menu: `files_title`, `contact_text`, `rules_text`, `services_text`, `referral_text`, `premium_text`, `news_text`
  - admin: `admin_users_title`, `admin_user_downloads_title`, `premium_set_ok`, `premium_unset_ok`, …
  - error: `error_generic`, `error_try_lower_quality`, …

## Verification
- اجرای تست‌های موجود:
  - `python -m unittest` در ریشه پروژه
- افزودن تست‌های جدید (unittest) برای:
  - محاسبه سهمیه و مصرف روزانه (با SQLite موقت)
  - لاجیک referral (ثبت فقط یک‌بار و افزایش bonus)
- تست دستی سناریوها:
  - کاربر جدید → انتخاب زبان → نمایش منوی اصلی
  - دانلود موفق → کم شدن حجم → نمایش در Stats
  - دانلود با حجم بیشتر از باقی‌مانده → عدم ارسال + پیام مناسب
  - ارورهای رایج yt-dlp → پیام user-friendly
  - ادمین /users → انتخاب کاربر → مشاهده history

