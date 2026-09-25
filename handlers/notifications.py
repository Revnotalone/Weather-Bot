# -*- coding: utf-8 -*-
"""
Pengaturan notifikasi push: ramalan harian, alert gempa, alert cuaca ekstrem.

Alur "ramalan harian" butuh 2 langkah (pilih kota -> pilih jam), jadi kota
yang sedang dipilih disimpan sementara di FSMContext data (bukan storage
permanen) sampai jam-nya juga dipilih dan baru disimpan sekaligus.
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import config
import keyboards as kb
from states import NotifFlow
from storage import JSONStorage
from texts import t
from weather_api import validate_city, InvalidCityError

router = Router(name="notifications")


def _notif_menu_text(lang: str, user: dict) -> str:
    daily = user.get("daily_notify", {})
    quake = user.get("quake_alert", {})
    extreme = user.get("extreme_weather_alert", {})
    lines = [t(lang, "notif_title"), ""]
    daily_status = t(lang, "status_on") if daily.get("enabled") else t(lang, "status_off")
    lines.append(t(lang, "notif_daily_status", status=daily_status))
    if daily.get("enabled"):
        lines.append(f"   📍 {daily.get('city')} — {daily.get('hour', 0):02d}:{daily.get('minute', 0):02d} WIB")
    quake_status = t(lang, "status_on") if quake.get("enabled") else t(lang, "status_off")
    lines.append(t(lang, "notif_quake_status", mag=quake.get("min_magnitude", config.DEFAULT_QUAKE_MIN_MAGNITUDE), status=quake_status))
    extreme_status = t(lang, "status_on") if extreme.get("enabled") else t(lang, "status_off")
    lines.append(t(lang, "notif_extreme_status", status=extreme_status))
    if extreme.get("enabled"):
        lines.append(f"   📍 {extreme.get('city')}")
    return "\n".join(lines)


async def _render_notif_menu(callback: CallbackQuery, storage: JSONStorage) -> None:
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    daily_on = user.get("daily_notify", {}).get("enabled", False)
    quake_on = user.get("quake_alert", {}).get("enabled", False)
    extreme_on = user.get("extreme_weather_alert", {}).get("enabled", False)
    await callback.message.edit_text(
        _notif_menu_text(lang, user),
        reply_markup=kb.notifications_menu(lang, daily_on, quake_on, extreme_on),
    )


@router.callback_query(F.data == "menu:notif")
async def show_notif_menu(callback: CallbackQuery, state: FSMContext, storage: JSONStorage):
    await state.clear()
    await _render_notif_menu(callback, storage)
    await callback.answer()


# ---------------------------------------------------------- ramalan harian --

@router.callback_query(F.data == "notif:daily:toggle")
async def toggle_daily(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    if user.get("daily_notify", {}).get("enabled"):
        storage.update_user(callback.from_user.id, daily_notify={"enabled": False})
        await callback.answer(t(lang, "notif_daily_off").replace("<b>", "").replace("</b>", ""))
        await _render_notif_menu(callback, storage)
        return

    favs = user.get("favorites", [])
    await callback.message.edit_text(
        t(lang, "notif_daily_set_city"),
        reply_markup=kb.pick_city_for_daily_keyboard(lang, favs),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dnc:"))
async def pick_daily_city(callback: CallbackQuery, state: FSMContext, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    choice = callback.data.split(":", 1)[1]

    if choice == "manual":
        await state.set_state(NotifFlow.waiting_daily_city_manual)
        await callback.message.edit_text(t(lang, "ask_city"), reply_markup=kb.ask_city_keyboard(lang))
        await callback.answer()
        return

    try:
        idx = int(choice)
        city = user.get("favorites", [])[idx]
    except (ValueError, IndexError):
        await callback.answer()
        return

    await state.update_data(pending_daily_city=city)
    await callback.message.edit_text(t(lang, "notif_daily_set_time"), reply_markup=kb.daily_hour_keyboard(lang))
    await callback.answer()


@router.message(StateFilter(NotifFlow.waiting_daily_city_manual), F.text)
async def receive_daily_city_manual(message: Message, state: FSMContext, storage: JSONStorage):
    user = storage.get_user(message.from_user.id)
    lang = user.get("lang", "id")
    try:
        city = validate_city(message.text)
    except InvalidCityError as e:
        await message.answer(t(lang, "invalid_city", error=str(e)))
        return

    await state.set_state(None)  # keluar dari state ini, tapi data pending tetap disimpan
    await state.update_data(pending_daily_city=city)
    await message.answer(t(lang, "notif_daily_set_time"), reply_markup=kb.daily_hour_keyboard(lang))


@router.callback_query(F.data.startswith("dnh:"))
async def pick_daily_hour(callback: CallbackQuery, state: FSMContext, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    data = await state.get_data()
    city = data.get("pending_daily_city") or user.get("last_city")
    if not city:
        await callback.answer(t(lang, "notif_daily_set_city"), show_alert=True)
        return

    try:
        hour = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer()
        return

    storage.update_user(
        callback.from_user.id,
        daily_notify={"enabled": True, "city": city, "hour": hour, "minute": 0, "last_sent_date": None},
    )
    await state.clear()
    await callback.answer(
        t(lang, "notif_daily_saved", city=city, hour=hour, minute=0)
        .replace("<b>", "").replace("</b>", "")
    )
    await _render_notif_menu(callback, storage)


# ------------------------------------------------------------- alert gempa --

@router.callback_query(F.data == "notif:quake:toggle")
async def toggle_quake(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    quake = user.get("quake_alert", {})
    new_enabled = not quake.get("enabled", False)
    min_mag = quake.get("min_magnitude") or config.DEFAULT_QUAKE_MIN_MAGNITUDE
    storage.update_user(callback.from_user.id, quake_alert={"enabled": new_enabled, "min_magnitude": min_mag})
    key = "notif_quake_on" if new_enabled else "notif_quake_off"
    await callback.answer(t(lang, key, mag=min_mag).replace("<b>", "").replace("</b>", ""))
    await _render_notif_menu(callback, storage)


@router.callback_query(F.data == "menu:quakemag")
async def show_quake_mag(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    current = user.get("quake_alert", {}).get("min_magnitude", config.DEFAULT_QUAKE_MIN_MAGNITUDE)
    await callback.message.edit_text(
        "🎚️ Pilih ambang magnitudo minimum untuk alert gempa:" if lang == "id"
        else "🎚️ Choose minimum magnitude threshold for earthquake alerts:",
        reply_markup=kb.quake_magnitude_keyboard(lang, current),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qmag:"))
async def set_quake_mag(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    try:
        mag = float(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer()
        return
    quake = user.get("quake_alert", {})
    storage.update_user(callback.from_user.id, quake_alert={"enabled": quake.get("enabled", False), "min_magnitude": mag})
    await callback.answer(f"✅ M{mag}")
    await callback.message.edit_text(
        "🎚️ Pilih ambang magnitudo minimum untuk alert gempa:" if lang == "id"
        else "🎚️ Choose minimum magnitude threshold for earthquake alerts:",
        reply_markup=kb.quake_magnitude_keyboard(lang, mag),
    )


# ------------------------------------------------------- alert cuaca ekstrem --

@router.callback_query(F.data == "notif:extreme:toggle")
async def toggle_extreme(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    extreme = user.get("extreme_weather_alert", {})

    if extreme.get("enabled"):
        storage.update_user(callback.from_user.id, extreme_weather_alert={"enabled": False})
        await callback.answer(t(lang, "notif_extreme_off").replace("<b>", "").replace("</b>", ""))
        await _render_notif_menu(callback, storage)
        return

    city = user.get("last_city")
    if not city:
        await callback.answer(t(lang, "ask_city"), show_alert=True)
        return

    storage.update_user(callback.from_user.id, extreme_weather_alert={
        "enabled": True, "city": city, "last_sent_at": None,
    })
    await callback.answer(t(lang, "notif_extreme_on", city=city).replace("<b>", "").replace("</b>", ""))
    await _render_notif_menu(callback, storage)
