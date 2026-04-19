from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def _fmt_mb(size_bytes: int) -> str:
    try:
        if not size_bytes:
            return ""
        mb = float(size_bytes) / (1024.0 * 1024.0)
        return f"~{mb:.2f}MB"
    except Exception:
        return ""

def language_menu():
    from bot.utils.locales import get_text
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text("en", "btn_lang_en"), callback_data="lang_en"),
                InlineKeyboardButton(text=get_text("en", "btn_lang_fa"), callback_data="lang_fa"),
            ]
        ]
    )

def download_quality_menu(lang: str, pending_id: int, video_options: list[dict] | None, duration_s: int | None):
    from bot.utils.locales import get_text
    video_options = list(video_options or [])
    video_options.sort(key=lambda x: int(x.get("height") or 0), reverse=True)

    heights = [int(v.get("height") or 0) for v in video_options if v.get("height")]
    recommended = 720 if 720 in heights else (480 if 480 in heights else (max(heights) if heights else 0))

    audio_rates = [128, 192, 320]
    audio_buttons = []
    for kbps in audio_rates:
        est = ""
        if duration_s:
            est_b = int((float(kbps) * 1000.0 / 8.0) * float(duration_s))
            est = _fmt_mb(est_b)
        text = f"⬇️ MP3 {kbps}"
        if est:
            text = f"{text}, {est}"
        audio_buttons.append(InlineKeyboardButton(text=text, callback_data=f"dl:{pending_id}:audio_{kbps}"))
    audio_buttons.append(InlineKeyboardButton(text="⬇️ MP3 Best", callback_data=f"dl:{pending_id}:audio_best"))

    rows = []
    max_rows = max(len(video_options), len(audio_buttons))
    max_rows = min(max_rows, 6)
    for i in range(max_rows):
        left = None
        if i < len(video_options):
            v = video_options[i]
            w = int(v.get("width") or 0)
            h = int(v.get("height") or 0)
            size = int(v.get("size_bytes") or 0)
            label = f"⬇️ {w}x{h}" if w else f"⬇️ {h}p"
            mb = _fmt_mb(size)
            if mb:
                label = f"{label}, {mb}"
            if h and h == recommended:
                label = f"⭐️ {label}"
            left = InlineKeyboardButton(text=label, callback_data=f"dl:{pending_id}:video_{h}" if h else f"dl:{pending_id}:video_best")

        right = audio_buttons[i] if i < len(audio_buttons) else None
        row = []
        if left:
            row.append(left)
        if right:
            row.append(right)
        if row:
            rows.append(row)

    rows.append([InlineKeyboardButton(text=get_text(lang, "btn_video_best"), callback_data=f"dl:{pending_id}:video_best")])
    rows.append([InlineKeyboardButton(text=get_text(lang, "btn_cancel"), callback_data=f"dl:{pending_id}:cancel")])

    return InlineKeyboardMarkup(inline_keyboard=rows)

def main_menu_inline(lang: str = 'en'):
    from bot.utils.locales import get_text
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, 'btn_files'), callback_data='menu_files')],
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_search'), switch_inline_query_current_chat=""),
                InlineKeyboardButton(text=get_text(lang, 'btn_settings'), callback_data='menu_settings')
            ],
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_contact'), callback_data='menu_contact'),
                InlineKeyboardButton(text=get_text(lang, 'btn_stats'), callback_data='menu_stats')
            ],
            [InlineKeyboardButton(text=get_text(lang, 'btn_how_to'), url="https://t.me/telegram")],
            [InlineKeyboardButton(text=get_text(lang, 'btn_rules'), callback_data='menu_rules')],
            [InlineKeyboardButton(text=get_text(lang, 'btn_services'), callback_data='menu_services')],
            [InlineKeyboardButton(text=get_text(lang, 'btn_referral'), callback_data='menu_referral')],
            [InlineKeyboardButton(text=get_text(lang, 'btn_premium'), callback_data='menu_premium')],
            [InlineKeyboardButton(text=get_text(lang, 'btn_news'), callback_data='menu_news')]
        ]
    )
    return keyboard

def settings_menu(lang: str = 'en'):
    from bot.utils.locales import get_text
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_video'), callback_data='set_mode_video'),
                InlineKeyboardButton(text=get_text(lang, 'btn_audio'), callback_data='set_mode_audio')
            ],
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_lang_en'), callback_data='lang_en'),
                InlineKeyboardButton(text=get_text(lang, 'btn_lang_fa'), callback_data='lang_fa')
            ],
            [InlineKeyboardButton(text="🔙", callback_data='menu_back')]
        ]
    )

def download_choice_menu(lang: str, pending_id: int):
    from bot.utils.locales import get_text
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_video_360'), callback_data=f'dl:{pending_id}:video_360'),
                InlineKeyboardButton(text=get_text(lang, 'btn_audio_128'), callback_data=f'dl:{pending_id}:audio_128'),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_video_480'), callback_data=f'dl:{pending_id}:video_480'),
                InlineKeyboardButton(text=get_text(lang, 'btn_audio_192'), callback_data=f'dl:{pending_id}:audio_192'),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_video_720'), callback_data=f'dl:{pending_id}:video_720'),
                InlineKeyboardButton(text=get_text(lang, 'btn_audio_320'), callback_data=f'dl:{pending_id}:audio_320'),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_video_1080'), callback_data=f'dl:{pending_id}:video_1080'),
                InlineKeyboardButton(text=get_text(lang, 'btn_audio_best'), callback_data=f'dl:{pending_id}:audio_best'),
            ],
            [InlineKeyboardButton(text=get_text(lang, 'btn_video_best'), callback_data=f'dl:{pending_id}:video_best')],
            [InlineKeyboardButton(text=get_text(lang, 'btn_cancel'), callback_data=f'dl:{pending_id}:cancel')],
        ]
    )

def pager_menu(lang: str, prev_cb: str | None, next_cb: str | None, back_cb: str | None = None):
    from bot.utils.locales import get_text
    rows = []
    nav = []
    if prev_cb:
        nav.append(InlineKeyboardButton(text=get_text(lang, "btn_prev"), callback_data=prev_cb))
    if next_cb:
        nav.append(InlineKeyboardButton(text=get_text(lang, "btn_next"), callback_data=next_cb))
    if nav:
        rows.append(nav)
    if back_cb:
        rows.append([InlineKeyboardButton(text=get_text(lang, "btn_back"), callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def users_list_menu(lang: str, users: list[tuple], page: int, has_next: bool):
    from bot.utils.locales import get_text
    rows = []
    for u in users:
        user_id = int(u[0])
        username = (u[1] or "").strip()
        label = f"@{username}" if username else str(user_id)
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_user:{user_id}:0")])
    prev_cb = f"admin_users:{page - 1}" if page > 0 else None
    next_cb = f"admin_users:{page + 1}" if has_next else None
    nav = []
    if prev_cb:
        nav.append(InlineKeyboardButton(text=get_text(lang, "btn_prev"), callback_data=prev_cb))
    if next_cb:
        nav.append(InlineKeyboardButton(text=get_text(lang, "btn_next"), callback_data=next_cb))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def user_downloads_menu(lang: str, user_id: int, page: int, has_next: bool):
    from bot.utils.locales import get_text
    prev_cb = f"admin_user:{user_id}:{page - 1}" if page > 0 else None
    next_cb = f"admin_user:{user_id}:{page + 1}" if has_next else None
    return pager_menu(lang, prev_cb, next_cb, back_cb=f"admin_users:{0}")
