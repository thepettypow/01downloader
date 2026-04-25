def to_user_friendly_error(lang: str, err: str) -> str:
    s = (err or "").strip()
    low = s.lower()

    def fa(t: str, e: str) -> str:
        return t if (lang or "").lower().startswith("fa") else e

    if not s:
        return fa("😬 یه چیزی پرید. یه کم بعد دوباره بزن.", "😬 Something went sideways. Try again in a bit.")

    if "facebook.com/login" in low or "facebook.com/login.php" in low:
        return fa(
            "😬 فیسبوک اجازه دانلود نمی‌ده (لاگین/کوکی لازم داره). اگه ویدیو پابلیکه، با cookies.txt تست کن.",
            "😬 Facebook blocked access (login/cookies required). If it’s public, try again with a valid cookies.txt.",
        )

    if "pinterest oembed" in low or "pinterest html" in low or "pinterest image http" in low:
        return fa(
            "😬 پینترست اجازه نداد عکس رو بگیرم (احتمالاً بلاک/403). یه بار دیگه تست کن یا با VPN/پروکسی سرور تست کن.",
            "😬 Pinterest blocked the image fetch (often 403/blocked). Try again or test from a different IP.",
        )

    if "unsupported url" in low or "unsupported link" in low or "not supported" in low:
        return fa("😅 این لینک رو ساپورت نمی‌کنم.", "😅 I can’t handle this link.")

    if "po token" in low or "po_token" in low or "youtubepot" in low or "bgutil" in low:
        return fa(
            "😬 یوتیوب PO Token می‌خواد. سرویس bgutil رو روشن کن و YTDLP_YOUTUBE_POT_BASE_URL رو ست کن.",
            "😬 YouTube needs a PO Token. Start the bgutil sidecar and set YTDLP_YOUTUBE_POT_BASE_URL.",
        )

    if "sign in to confirm you" in low or "confirm you’re not a bot" in low or "confirm you're not a bot" in low:
        return fa(
            "😬 یوتیوب گیر داده (ضدبات). راه‌حل بدون پروکسی پولی: PO Token (bgutil) + چندتا cookies.txt و MAX_CONCURRENT_DOWNLOADS=1.",
            "😬 YouTube blocked the server (anti-bot). No-paid-proxy fix: PO Token (bgutil) + a cookie pool + MAX_CONCURRENT_DOWNLOADS=1.",
        )

    if "private" in low or "login" in low or "sign in" in low or "cookies" in low or "confirm you" in low:
        return fa(
            "😬 سایت مقصد گیر داده (لاگین/کوکی یا ضدبات). یه کم بعد دوباره بزن یا کیفیت پایین‌تر انتخاب کن.",
            "😬 The site blocked access (login/cookies/anti-bot). Try again later or pick a lower quality.",
        )

    if "geo" in low or "not available in your country" in low:
        return fa("😅 این یکی به خاطر محدودیت منطقه‌ای نمیاد.", "😅 Geo restriction. Can’t grab this one.")

    if "timed out" in low or "timeout" in low:
        return fa("⏳ خیلی طول کشید و قطع شد. یه بار با کیفیت پایین‌تر بزن.", "⏳ Took too long and timed out. Try a lower quality.")

    if "no matches found on youtube" in low or "no matches found" in low:
        return fa("😬 تو یوتیوب براش چیزی پیدا نکردم. یه کم بعد دوباره بزن یا spotdl رو روشن کن.", "😬 Couldn’t find a good match on YouTube. Try later or enable spotdl.")

    if "http error" in low:
        return fa("😬 لینک مستقیم مشکل داره یا سرورش قاطی کرده.", "😬 Direct link/server error.")

    if "request entity too large" in low or "file is larger than 2gb" in low or "cannot be uploaded" in low:
        return fa("😅 این فایل خیلی گنده‌ست برای تلگرام. کیفیت پایین‌تر بزن.", "😅 Too big for Telegram. Pick a lower quality.")

    if "connection" in low or "network" in low or "bad gateway" in low or "service unavailable" in low:
        return fa("😬 شبکه/سرور یه لحظه قاطی کرد. یه کم بعد دوباره بزن.", "😬 Network/server hiccup. Try again soon.")

    return fa("😬 دانلود نشد. یه کم بعد دوباره بزن.", "😬 Didn’t work. Try again later.")
