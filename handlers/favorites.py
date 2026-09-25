# -*- coding: utf-8 -*-
"""Kelola kota favorit: lihat daftar, buka cuaca cepat, hapus."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

import keyboards as kb
from handlers.weather import show_weather_card
from storage import JSONStorage
from texts import t
from weather_api import WeatherClient

router = Router(name="favorites")


@router.callback_query(F.data == "menu:fav")
async def show_favorites(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    favs = user.get("favorites", [])
    if not favs:
        await callback.message.edit_text(t(lang, "fav_empty"), reply_markup=kb.favorites_keyboard(lang, []))
    else:
        await callback.message.edit_text(t(lang, "fav_title"), reply_markup=kb.favorites_keyboard(lang, favs))
    await callback.answer()


@router.callback_query(F.data.startswith("favgo:"))
async def open_favorite(callback: CallbackQuery, storage: JSONStorage, client: WeatherClient):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    favs = user.get("favorites", [])
    try:
        idx = int(callback.data.split(":", 1)[1])
        city = favs[idx]
    except (ValueError, IndexError):
        await callback.answer()
        return
    await callback.answer()
    await show_weather_card(callback.bot, callback.message.chat.id, callback.from_user.id,
                              city, lang, storage, client)


@router.callback_query(F.data.startswith("favdel:"))
async def delete_favorite(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    favs = user.get("favorites", [])
    try:
        idx = int(callback.data.split(":", 1)[1])
        city = favs[idx]
    except (ValueError, IndexError):
        await callback.answer()
        return

    storage.remove_favorite(callback.from_user.id, city)
    updated = storage.get_user(callback.from_user.id).get("favorites", [])
    await callback.answer(t(lang, "fav_removed", city=city).replace("<b>", "").replace("</b>", ""))
    if updated:
        await callback.message.edit_text(t(lang, "fav_title"), reply_markup=kb.favorites_keyboard(lang, updated))
    else:
        await callback.message.edit_text(t(lang, "fav_empty"), reply_markup=kb.favorites_keyboard(lang, []))
