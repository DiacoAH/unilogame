import asyncio
import json
import logging
import os
import urllib.request

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

WEBAPP_URL = os.environ['WEBAPP_URL']
BOT_TOKEN = os.environ['BOT_TOKEN']
INTERNAL_API_SECRET = os.environ.get('INTERNAL_API_SECRET', '')
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://web:8000')

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def register_user(telegram_id: int) -> None:
    """Best-effort: register the user in the backend via internal API."""
    if not INTERNAL_API_SECRET:
        logging.warning('INTERNAL_API_SECRET not set; skipping user registration')
        return

    url = BACKEND_URL + '/api/internal/users/'
    payload = json.dumps({'telegram_id': telegram_id}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'X-Internal-Secret': INTERNAL_API_SECRET,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            logging.info('Registered user %s: HTTP %s', telegram_id, resp.status)
    except Exception as exc:
        logging.warning('Failed to register user %s: %s', telegram_id, exc)


@dp.message(CommandStart())
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Play', web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await message.answer('Welcome, commander! Open your solar system:', reply_markup=kb)
    register_user(message.from_user.id)


async def main():
    logging.basicConfig(level=logging.INFO)
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text='Play', web_app=WebAppInfo(url=WEBAPP_URL))
    )
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
