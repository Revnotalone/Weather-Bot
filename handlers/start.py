# -*- coding: utf-8 -*-
"""/start, navigasi ke menu utama, dan bantuan."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import keyboards as kb
from storage import JSONStorage
from texts import t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, storage: JSONStorage):
    await state.clear()
    user = storage.get_user(message.from_user.id)
    lang = user.get("lang", "id")
    name = message.from_user.first_name or "kamu"
    await message.answer(t(lang, "welcome", name=name), reply_markup=kb.main_menu(lang))


@router.callback_query(F.data == "menu:home")
async def go_home(callback: CallbackQuery, state: FSMContext, storage: JSONStorage):
    await state.clear()
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    await callback.message.edit_text(t(lang, "main_menu_title"), reply_markup=kb.main_menu(lang))
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def show_help(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    bot_info = await callback.bot.get_me()
    text = t(lang, "help_text", bot_username=bot_info.username)
    await callback.message.edit_text(text, reply_markup=kb.help_keyboard(lang))
    await callback.answer()
