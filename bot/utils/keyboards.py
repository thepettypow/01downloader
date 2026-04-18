from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
                InlineKeyboardButton(text=get_text(lang, 'btn_video'), callback_data=f'dl:{pending_id}:video'),
                InlineKeyboardButton(text=get_text(lang, 'btn_audio'), callback_data=f'dl:{pending_id}:audio'),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, 'btn_document'), callback_data=f'dl:{pending_id}:document'),
                InlineKeyboardButton(text=get_text(lang, 'btn_cancel'), callback_data=f'dl:{pending_id}:cancel'),
            ],
        ]
    )
