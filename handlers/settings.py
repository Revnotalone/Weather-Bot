# -*- coding: utf-8 -*-
"""Pengaturan: satuan suhu (°C/°F) dan bahasa (ID/EN)."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

import keyboards as kb
from storage import JSONStorage
from texts import t

router = Router(name="settings")

UNIT_LABELS = {"c": "°C (Celsius)", "f": "°F (Fahrenheit)"}
LANG_LABELS = {"id": "Bahasa Indonesia", "en": "English"}


@router.callback_query(F.data == "menu:settings")
async def show_settings(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang, unit = user.get("lang", "id"), user.get("unit", "c")
    text = (
        f"{t(lang, 'settings_title')}\n\n"
        f"{t(lang, 'settings_unit', unit=UNIT_LABELS[unit])}\n"
        f"{t(lang, 'settings_lang', lang_label=LANG_LABELS[lang])}"
    )
    await callback.message.edit_text(text, reply_markup=kb.settings_menu(lang, unit, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("settings:unit:"))
async def change_unit(callback: CallbackQuery, storage: JSONStorage):
    new_unit = callback.data.split(":")[-1]
    user = storage.update_user(callback.from_user.id, unit=new_unit)
    lang = user.get("lang", "id")
    await callback.answer(t(lang, "settings_unit_changed", unit=UNIT_LABELS[new_unit]).replace("<b>", "").replace("</b>", ""))
    text = (
        f"{t(lang, 'settings_title')}\n\n"
        f"{t(lang, 'settings_unit', unit=UNIT_LABELS[new_unit])}\n"
        f"{t(lang, 'settings_lang', lang_label=LANG_LABELS[lang])}"
    )
    await callback.message.edit_text(text, reply_markup=kb.settings_menu(lang, new_unit, lang))


@router.callback_query(F.data.startswith("settings:lang:"))
async def change_lang(callback: CallbackQuery, storage: JSONStorage):
    new_lang = callback.data.split(":")[-1]
    user = storage.update_user(callback.from_user.id, lang=new_lang)
    unit = user.get("unit", "c")
    await callback.answer(t(new_lang, "settings_lang_changed", lang_label=LANG_LABELS[new_lang]).replace("<b>", "").replace("</b>", ""))
    text = (
        f"{t(new_lang, 'settings_title')}\n\n"
        f"{t(new_lang, 'settings_unit', unit=UNIT_LABELS[unit])}\n"
        f"{t(new_lang, 'settings_lang', lang_label=LANG_LABELS[new_lang])}"
    )
    await callback.message.edit_text(text, reply_markup=kb.settings_menu(new_lang, unit, new_lang))
