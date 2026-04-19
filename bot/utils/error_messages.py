def to_user_friendly_error(lang: str, err: str) -> str:
    s = (err or "").strip()
    low = s.lower()

    def fa(t: str, e: str) -> str:
        return t if (lang or "").lower().startswith("fa") else e

    if not s:
        return fa("دانلود ناموفق بود. لطفاً بعداً دوباره تلاش کنید.", "Download failed. Please try again later.")

    if "unsupported url" in low or "unsupported link" in low or "not supported" in low:
        return fa("این لینک پشتیبانی نمی‌شود.", "This link is not supported.")

    if "private" in low or "login" in low or "sign in" in low or "cookies" in low or "confirm you" in low:
        return fa(
            "سایت مقصد دسترسی را محدود کرده (نیاز به ورود/کوکی یا محدودیت ضدبات). لطفاً بعداً دوباره تلاش کنید یا کیفیت پایین‌تر انتخاب کنید.",
            "The site blocked access (login/cookies or anti-bot). Please try again later or choose a lower quality.",
        )

    if "geo" in low or "not available in your country" in low:
        return fa("این محتوا به دلیل محدودیت منطقه‌ای قابل دانلود نیست.", "This content is not available due to geo restriction.")

    if "timed out" in low or "timeout" in low:
        return fa("دانلود/پردازش زمان‌بر شد. لطفاً کیفیت پایین‌تر انتخاب کنید و دوباره تلاش کنید.", "Download/processing timed out. Try a lower quality and retry.")

    if "no matches found on youtube" in low or "no matches found" in low:
        return fa("برای این مورد در جستجوی یوتیوب نتیجه‌ای پیدا نشد. لطفاً بعداً دوباره تلاش کنید یا از حالت spotdl استفاده کنید.", "No matches were found on YouTube for this Spotify item. Try again later or enable spotdl.")

    if "http error" in low:
        return fa("لینک مستقیم معتبر نیست یا سرور فایل خطا داد.", "The direct link is not valid or the server returned an error.")

    if "request entity too large" in low or "file is larger than 2gb" in low or "cannot be uploaded" in low:
        return fa("حجم فایل برای ارسال در تلگرام زیاد است. لطفاً کیفیت پایین‌تر انتخاب کنید.", "File is too large to upload to Telegram. Please choose a lower quality.")

    if "connection" in low or "network" in low or "bad gateway" in low or "service unavailable" in low:
        return fa("مشکل موقت شبکه/سرور. لطفاً کمی بعد دوباره تلاش کنید.", "Temporary network/server issue. Please try again later.")

    return fa("دانلود ناموفق بود. لطفاً بعداً دوباره تلاش کنید.", "Download failed. Please try again later.")
