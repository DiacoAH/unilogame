import asyncio
import logging
import os

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
bot = Bot(os.environ['BOT_TOKEN'])
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Play', web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await message.answer('Welcome, commander! Open your solar system:', reply_markup=kb)


async def main():
    logging.basicConfig(level=logging.INFO)
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text='Play', web_app=WebAppInfo(url=WEBAPP_URL))
    )
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
