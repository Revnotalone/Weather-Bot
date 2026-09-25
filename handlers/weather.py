# -*- coding: utf-8 -*-
"""
Handler inti: alur cek cuaca. Semua entry point (ketik nama kota, tombol
favorit, tombol refresh, kirim lokasi) berakhir memanggil `show_weather_card()`
supaya tidak ada duplikasi logika fetch+render+kirim.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import keyboards as kb
from animations import LoadingAnimator, react_to_message
from charts import render_hourly_chart
from states import WeatherFlow
from storage import JSONStorage
from texts import t
from weather_api import WeatherClient, DataSourceError, InvalidCityError, weather_icon, extract_area_name
from weather_render import (
    format_weather_message, format_forecast_message,
    format_earthquake_detail_message, compute_status_alerts, format_status_banner,
)

logger = logging.getLogger("weatherbot.handlers.weather")
router = Router(name="weather")


async def _fetch_bundle(client: WeatherClient, city: str, animator: LoadingAnimator,
                          prefetched_weather: dict | None = None):
    """Ambil semua data terkait satu kota, dengan animasi progres bertahap.
    Melempar DataSourceError/InvalidCityError kalau cuaca (data wajib) gagal total.
    `prefetched_weather` dipakai saat data cuaca sudah diambil sebelumnya
    (misal alur kirim lokasi, yang butuh fetch cuaca duluan untuk resolve
    nama area sebelum kartu ditampilkan) — supaya tidak fetch dua kali."""
    await animator.step("cuaca", percent=15)
    weather_data = prefetched_weather or await asyncio.to_thread(client.get_weather, city)

    lat = lon = 0.0
    area = weather_data.get("nearest_area", [])
    if area:
        try:
            lat = float(area[0].get("latitude", "0"))
            lon = float(area[0].get("longitude", "0"))
        except (ValueError, TypeError, IndexError):
            pass

    await animator.step("kualitas udara", percent=45)
    aqi_data = await asyncio.to_thread(client.get_air_quality, lat, lon) if (lat and lon) else None

    await animator.step("gempa & peringatan dini", percent=75)
    eq_latest, warnings = await asyncio.gather(
        asyncio.to_thread(client.get_earthquake_latest),
        asyncio.to_thread(client.get_bmkg_warnings),
    )

    await animator.step("menyusun laporan", percent=95)
    return weather_data, aqi_data, eq_latest, warnings, lat, lon


async def show_weather_card(bot, chat_id: int, user_id: int, city: str, lang: str,
                              storage: JSONStorage, client: WeatherClient,
                              prefetched_weather: dict | None = None,
                              display_name: str | None = None) -> None:
    """`city` adalah query yang dipakai untuk fetch (bisa nama kota ATAU
    "lat,lon"). `display_name`, kalau diisi, dipakai untuk teks/tombol/
    penyimpanan favorit — supaya user tidak pernah lihat angka koordinat
    mentah di layar walau query-nya memang koordinat."""
    label = display_name or city
    user = storage.get_user(user_id)
    unit = user.get("unit", "c")
    animator = LoadingAnimator(bot, chat_id, lang, __import__("texts"))
    await animator.start("cuaca", percent=10)

    try:
        weather_data, aqi_data, eq_latest, warnings, lat, lon = await _fetch_bundle(
            client, city, animator, prefetched_weather=prefetched_weather
        )
    except InvalidCityError as e:
        await animator.reveal(t(lang, "invalid_city", error=str(e)))
        return
    except DataSourceError:
        await animator.reveal(t(lang, "city_not_found", city=label))
        return
    except Exception:
        logger.exception("Kegagalan tak terduga saat fetch cuaca untuk kota=%s", city)
        await animator.reveal(t(lang, "generic_error"))
        return

    await animator.finish()

    # Simpan sebagai konteks aktif user (dipakai wx:refresh/chart/forecast/export/dst).
    # Sengaja simpan LABEL (nama), bukan query mentah, supaya refresh/favorit
    # berikutnya jalan seperti pencarian kota normal.
    storage.update_user(user_id, last_city=label, last_lat=lat, last_lon=lon)

    alerts = compute_status_alerts(lang, weather_data, aqi_data, eq_latest, warnings)
    banner = format_status_banner(lang, alerts)
    card = format_weather_message(lang, unit, label, weather_data, aqi_data)
    full_text = f"{banner}\n\n{card}" if alerts else card

    favorites = [f.lower() for f in user.get("favorites", [])]
    is_fav = label.lower() in favorites
    markup = kb.weather_card_keyboard(lang, label, is_fav)

    await animator.reveal(full_text, reply_markup=markup)

    # Sentuhan kecil: kasih reaction otomatis kalau ada kondisi ekstrem.
    if alerts:
        try:
            await react_to_message(bot, chat_id, animator.message.message_id, "🔥")
        except Exception:  # noqa: BLE001 - reaction kosmetik, jangan sampai ganggu flow
            pass


# ------------------------------------------------------------------ entry points --

@router.callback_query(F.data == "menu:weather")
async def ask_city(callback: CallbackQuery, state: FSMContext, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    await state.set_state(WeatherFlow.waiting_city)
    await callback.message.edit_text(t(lang, "ask_city"), reply_markup=kb.ask_city_keyboard(lang))
    # Tawarkan juga opsi kirim lokasi lewat reply keyboard (jenis tombol
    # request_location cuma bisa muncul di reply keyboard, bukan inline).
    await callback.bot.send_message(
        callback.message.chat.id, t(lang, "share_location_prompt"),
        reply_markup=kb.share_location_keyboard(lang),
    )
    await callback.answer()


@router.message(StateFilter(WeatherFlow.waiting_city), F.text)
async def receive_city_text(message: Message, state: FSMContext, storage: JSONStorage, client: WeatherClient):
    await state.clear()
    user = storage.get_user(message.from_user.id)
    lang = user.get("lang", "id")
    await show_weather_card(message.bot, message.chat.id, message.from_user.id,
                              message.text.strip(), lang, storage, client)


@router.message(F.location)
async def receive_location(message: Message, storage: JSONStorage, client: WeatherClient):
    """User kirim lokasi lewat tombol 📍 Kirim Lokasi Saya.

    Alur resolusi nama tempat (biar user tidak pernah lihat angka
    koordinat mentah di kartu cuaca):
      1. Fetch cuaca pakai "lat,lon" ke wttr.in (paling akurat utk cuaca).
      2. Coba ambil nama area dari respons wttr.in itu sendiri (gratis,
         tidak perlu panggilan API tambahan).
      3. Kalau kosong, baru fallback ke reverse-geocoding Nominatim.
      4. Kalau itu pun gagal, tampilkan apa adanya (koordinat) — tetap
         tidak pernah crash.
    """
    user = storage.get_user(message.from_user.id)
    lang = user.get("lang", "id")
    loc = message.location
    coords_query = f"{loc.latitude},{loc.longitude}"

    await message.bot.send_chat_action(message.chat.id, "typing")
    try:
        weather_data = await asyncio.to_thread(client.get_weather, coords_query)
    except (InvalidCityError, DataSourceError):
        await message.answer(t(lang, "generic_error"))
        return
    except Exception:
        logger.exception("Kegagalan tak terduga saat fetch cuaca dari lokasi %s", coords_query)
        await message.answer(t(lang, "generic_error"))
        return

    display_name = extract_area_name(weather_data)
    if not display_name:
        display_name = await asyncio.to_thread(client.resolve_location_name, loc.latitude, loc.longitude)
    if not display_name:
        display_name = coords_query  # jaring pengaman terakhir, tetap tampil sesuatu

    await show_weather_card(message.bot, message.chat.id, message.from_user.id,
                              coords_query, lang, storage, client,
                              prefetched_weather=weather_data, display_name=display_name)


@router.message(F.text, StateFilter(None))
async def receive_plain_city_text(message: Message, storage: JSONStorage, client: WeatherClient):
    """Kalau user langsung ketik nama kota tanpa lewat menu dulu (tanpa FSM
    state aktif dan bukan command), tetap dianggap permintaan cek cuaca."""
    text = message.text.strip()
    if text.startswith("/"):
        return  # command tak dikenal, biarkan lolos (tidak ada handler lain = diabaikan)
    user = storage.get_user(message.from_user.id)
    lang = user.get("lang", "id")
    await show_weather_card(message.bot, message.chat.id, message.from_user.id,
                              text, lang, storage, client)


# ------------------------------------------------------------------ wx:* callbacks --

@router.callback_query(F.data == "wx:refresh")
async def wx_refresh(callback: CallbackQuery, storage: JSONStorage, client: WeatherClient):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    city = user.get("last_city")
    if not city:
        await callback.answer(t(lang, "ask_city"), show_alert=True)
        return
    await callback.answer("🔄")
    await show_weather_card(callback.bot, callback.message.chat.id, callback.from_user.id,
                              city, lang, storage, client)


@router.callback_query(F.data.in_({"wx:addfav", "wx:delfav"}))
async def wx_toggle_favorite(callback: CallbackQuery, storage: JSONStorage):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    city = user.get("last_city")
    if not city:
        await callback.answer()
        return

    if callback.data == "wx:addfav":
        storage.add_favorite(callback.from_user.id, city)
        await callback.answer(t(lang, "fav_added", city=city).replace("<b>", "").replace("</b>", ""))
        is_fav = True
    else:
        storage.remove_favorite(callback.from_user.id, city)
        await callback.answer(t(lang, "fav_removed", city=city).replace("<b>", "").replace("</b>", ""))
        is_fav = False

    try:
        await callback.message.edit_reply_markup(reply_markup=kb.weather_card_keyboard(lang, city, is_fav))
    except Exception:  # noqa: BLE001 - kalau pesan sudah berubah/dihapus, tidak fatal
        pass


@router.callback_query(F.data == "wx:chart")
async def wx_chart(callback: CallbackQuery, storage: JSONStorage, client: WeatherClient):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    unit = user.get("unit", "c")
    city = user.get("last_city")
    if not city:
        await callback.answer()
        return
    await callback.answer()
    await callback.bot.send_chat_action(callback.message.chat.id, "upload_photo")
    try:
        weather_data = await asyncio.to_thread(client.get_weather, city)
        today = weather_data.get("weather", [{}])[0]
        png_bytes = await asyncio.to_thread(render_hourly_chart, today.get("hourly", []), city, unit)
        photo = BufferedInputFile(png_bytes, filename=f"chart_{city}.png")
        await callback.bot.send_photo(callback.message.chat.id, photo)
    except (DataSourceError, ValueError, InvalidCityError):
        await callback.bot.send_message(callback.message.chat.id, t(lang, "city_not_found", city=city))
    except Exception:
        logger.exception("Gagal membuat grafik untuk kota=%s", city)
        await callback.bot.send_message(callback.message.chat.id, t(lang, "generic_error"))


@router.callback_query(F.data == "wx:forecast")
async def wx_forecast(callback: CallbackQuery, storage: JSONStorage, client: WeatherClient):
    user = storage.get_user(callback.from_user.id)
    lang, unit = user.get("lang", "id"), user.get("unit", "c")
    city = user.get("last_city")
    if not city:
        await callback.answer()
        return
    await callback.answer()
    try:
        weather_data = await asyncio.to_thread(client.get_weather, city)
        text = format_forecast_message(lang, unit, city, weather_data.get("weather", []))
        await callback.bot.send_message(callback.message.chat.id, text, parse_mode="HTML")
    except (DataSourceError, InvalidCityError):
        await callback.bot.send_message(callback.message.chat.id, t(lang, "city_not_found", city=city))
    except Exception:
        logger.exception("Gagal ambil ramalan untuk kota=%s", city)
        await callback.bot.send_message(callback.message.chat.id, t(lang, "generic_error"))


@router.callback_query(F.data == "wx:eqmore")
async def wx_earthquake_more(callback: CallbackQuery, storage: JSONStorage, client: WeatherClient):
    user = storage.get_user(callback.from_user.id)
    lang = user.get("lang", "id")
    await callback.answer()
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    eq_latest, eq_list, eq_felt = await asyncio.gather(
        asyncio.to_thread(client.get_earthquake_latest),
        asyncio.to_thread(client.get_earthquake_recent_list, 5),
        asyncio.to_thread(client.get_earthquake_felt, 5),
    )
    text = format_earthquake_detail_message(lang, eq_latest, eq_list, eq_felt)
    await callback.bot.send_message(callback.message.chat.id, text, parse_mode="HTML")


@router.callback_query(F.data == "wx:share")
async def wx_share_noop(callback: CallbackQuery):
    # Tombol share sebenarnya pakai switch_inline_query (ditangani native oleh
    # Telegram client, tidak sampai ke sini). Handler ini jaga-jaga saja.
    await callback.answer()
