# -*- coding: utf-8 -*-
"""
Semua inline keyboard bot, dipisah dari handler.

Prinsip callback_data yang dipakai di sini (penting, Telegram membatasi
callback_data maksimal 64 byte):
  - Aksi tetap (refresh, chart, forecast, dll) TIDAK menyimpan nama kota di
    callback_data — bot selalu merujuk ke `last_city` milik user yang
    tersimpan di storage. Jadi callback_data selalu pendek & konstan.
  - Favorit dirujuk lewat INDEX di list, bukan nama kota
    (`favgo:3`, `favdel:3`), supaya aman walau nama kota panjang.

Skema prefix:
  menu:<target>          navigasi antar menu
  wx:<action>             aksi di kartu cuaca (refresh/chart/forecast/addfav/...)
  favgo:<idx> favdel:<idx> aksi di daftar favorit
  notif:<kind>:<action>   toggle/atur notifikasi
  dnh:<hour>               pilih jam ramalan harian
  qmag:<value>             pilih ambang magnitudo gempa
  settings:unit:<c|f>      ganti satuan suhu
  settings:lang:<id|en>    ganti bahasa
"""
from __future__ import annotations

from typing import List

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from texts import t


def main_menu(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_check_weather"), callback_data="menu:weather")
    b.button(text=t(lang, "btn_favorites"), callback_data="menu:fav")
    b.button(text=t(lang, "btn_notifications"), callback_data="menu:notif")
    b.button(text=t(lang, "btn_settings"), callback_data="menu:settings")
    b.button(text=t(lang, "btn_help"), callback_data="menu:help")
    b.adjust(2, 2, 1)
    return b.as_markup()


def back_home_row(lang: str, extra_back_target: str | None = None) -> InlineKeyboardBuilder:
    """Baris navigasi standar dipakai di hampir semua menu."""
    b = InlineKeyboardBuilder()
    if extra_back_target:
        b.button(text=t(lang, "btn_back"), callback_data=extra_back_target)
    b.button(text=t(lang, "btn_home"), callback_data="menu:home")
    b.adjust(2 if extra_back_target else 1)
    return b


def weather_card_keyboard(lang: str, city: str, is_favorite: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_refresh"), callback_data="wx:refresh")
    fav_text = t(lang, "btn_remove_favorite") if is_favorite else t(lang, "btn_add_favorite")
    b.button(text=fav_text, callback_data="wx:delfav" if is_favorite else "wx:addfav")
    b.button(text=t(lang, "btn_hourly_chart"), callback_data="wx:chart")
    b.button(text=t(lang, "btn_forecast"), callback_data="wx:forecast")
    b.button(text=t(lang, "btn_earthquake_more"), callback_data="wx:eqmore")
    b.button(text=t(lang, "btn_export"), callback_data="wx:export")
    b.button(text=t(lang, "btn_share"), switch_inline_query=city)
    b.button(text=t(lang, "btn_home"), callback_data="menu:home")
    b.adjust(2, 2, 2, 1, 1)
    return b.as_markup()


def favorites_keyboard(lang: str, favorites: List[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for idx, city in enumerate(favorites):
        b.button(text=f"🌤️ {city}", callback_data=f"favgo:{idx}")
        b.button(text="🗑️", callback_data=f"favdel:{idx}")
    rows = [2] * len(favorites)
    b.button(text=t(lang, "btn_check_weather"), callback_data="menu:weather")
    b.button(text=t(lang, "btn_home"), callback_data="menu:home")
    b.adjust(*rows, 2)
    return b.as_markup()


def notifications_menu(lang: str, daily_on: bool, quake_on: bool, extreme_on: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=("✅ " if daily_on else "⭕ ") + t(lang, "notif_daily_label"),
        callback_data="notif:daily:toggle",
    )
    b.button(
        text=("✅ " if quake_on else "⭕ ") + t(lang, "notif_quake_label"),
        callback_data="notif:quake:toggle",
    )
    b.button(
        text=("✅ " if extreme_on else "⭕ ") + t(lang, "notif_extreme_label"),
        callback_data="notif:extreme:toggle",
    )
    if quake_on:
        b.button(text="🎚️ Atur Ambang Magnitudo" if lang == "id" else "🎚️ Set Magnitude Threshold",
                  callback_data="menu:quakemag")
    b.button(text=t(lang, "btn_home"), callback_data="menu:home")
    b.adjust(1, 1, 1, 1, 1)
    return b.as_markup()


def quake_magnitude_keyboard(lang: str, current: float) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for mag in (4.5, 5.0, 5.5, 6.0, 6.5, 7.0):
        prefix = "🔘" if abs(mag - current) < 0.01 else "⚪"
        b.button(text=f"{prefix} M{mag}", callback_data=f"qmag:{mag}")
    b.button(text=t(lang, "btn_back"), callback_data="menu:notif")
    b.adjust(3, 3, 1)
    return b.as_markup()


def daily_hour_keyboard(lang: str, favorites_hint: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for h in range(0, 24):
        b.button(text=f"{h:02d}:00", callback_data=f"dnh:{h}")
    b.button(text=t(lang, "btn_back"), callback_data="menu:notif")
    b.adjust(*([6] * 4), 1)
    return b.as_markup()


def pick_city_for_daily_keyboard(lang: str, favorites: List[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for idx, city in enumerate(favorites):
        b.button(text=f"🌤️ {city}", callback_data=f"dnc:{idx}")
    b.button(
        text=("✍️ Ketik kota lain" if lang == "id" else "✍️ Type another city"),
        callback_data="dnc:manual",
    )
    b.button(text=t(lang, "btn_back"), callback_data="menu:notif")
    b.adjust(*([1] * len(favorites)), 1, 1)
    return b.as_markup()


def settings_menu(lang: str, current_unit: str, current_lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=("🔘 °C" if current_unit == "c" else "⚪ °C"), callback_data="settings:unit:c")
    b.button(text=("🔘 °F" if current_unit == "f" else "⚪ °F"), callback_data="settings:unit:f")
    b.button(text=("🔘 Indonesia" if current_lang == "id" else "⚪ Indonesia"), callback_data="settings:lang:id")
    b.button(text=("🔘 English" if current_lang == "en" else "⚪ English"), callback_data="settings:lang:en")
    b.button(text=t(lang, "btn_home"), callback_data="menu:home")
    b.adjust(2, 2, 1)
    return b.as_markup()


def help_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_home"), callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def ask_city_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_home"), callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def share_location_keyboard(lang: str):
    """Reply keyboard (bukan inline) khusus untuk minta share lokasi — perlu
    tombol native Telegram request_location yang cuma bisa di reply keyboard."""
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    b = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(
            text="📍 " + ("Kirim Lokasi Saya" if lang == "id" else "Send My Location"),
            request_location=True,
        )]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    return b
