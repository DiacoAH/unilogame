import asyncio
import json
import logging
import os
import urllib.request

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
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
BOT_USERNAME = os.environ.get('BOT_USERNAME', '')

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def register_user(telegram_id: int, referred_by: str | None = None) -> None:
    """Best-effort: register the user in the backend via internal API."""
    if not INTERNAL_API_SECRET:
        logging.warning('INTERNAL_API_SECRET not set; skipping user registration')
        return

    url = BACKEND_URL + '/api/internal/users/'
    payload = json.dumps({'telegram_id': telegram_id, 'referred_by': referred_by}).encode()
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
    # Parse deep-link referral payload: /start ref<code>
    referred_by = None
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].startswith('ref'):
        referred_by = parts[1][3:]
    register_user(message.from_user.id, referred_by)


@dp.message(Command(commands=['referral']))
async def cmd_referral(message: Message):
    """Send the user's personal referral deep link."""
    global BOT_USERNAME
    if not BOT_USERNAME:
        try:
            me = await bot.me()
            BOT_USERNAME = me.username
        except Exception as exc:
            logging.warning('Could not detect bot username: %s', exc)
    if not BOT_USERNAME:
        await message.answer('Referral link unavailable: bot username not configured.')
        return

    url = BACKEND_URL + f'/api/internal/users/{message.from_user.id}/'
    req = urllib.request.Request(
        url,
        headers={'X-Internal-Secret': INTERNAL_API_SECRET},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            code = data.get('referral_code')
    except Exception as exc:
        logging.warning('Failed to fetch referral code for user %s: %s',
                        message.from_user.id, exc)
        await message.answer('Could not retrieve your referral link. Please try again later.')
        return

    if not code:
        await message.answer('You do not have a referral code yet. Start the bot with /start first.')
        return

    deep_link = f'https://t.me/{BOT_USERNAME}?start=ref{code}'
    await message.answer(deep_link)


async def main():
    global BOT_USERNAME
    logging.basicConfig(level=logging.INFO)
    if not BOT_USERNAME:
        try:
            me = await bot.me()
            BOT_USERNAME = me.username
            logging.info('Detected bot username: %s', BOT_USERNAME)
        except Exception as exc:
            logging.warning('Could not detect bot username at startup: %s', exc)
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text='Play', web_app=WebAppInfo(url=WEBAPP_URL))
    )
    # Register bot commands, best-effort.
    try:
        await bot.set_my_commands([
            BotCommand(command='start', description='Start the bot'),
            BotCommand(command='referral', description='Get your referral link'),
        ])
        logging.info('Bot commands registered')
    except Exception as exc:
        logging.warning('Failed to set bot commands: %s', exc)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
