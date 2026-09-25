# -*- coding: utf-8 -*-
"""
Scheduler notifikasi push — tiga job, semua jalan di background tanpa
mengganggu bot utama:

  1. daily_forecast_job   : tiap menit, cek user yang jadwalnya cocok
                             dengan jam:menit sekarang (WIB), kirim ramalan.
  2. quake_alert_job       : tiap SCHEDULER_TICK_SECONDS, cek apakah ada
                             gempa BARU (dibanding terakhir kali dicek),
                             kalau ya broadcast ke user yang subscribe &
                             magnitudonya memenuhi ambang.
  3. extreme_weather_job   : tiap 30 menit, cek kondisi ekstrem di kota
                             yang di-subscribe tiap user, dengan cooldown
                             supaya tidak spam notifikasi yang sama berulang.

Semua fetch API dikelompokkan per KOTA UNIK dulu (bukan per user) supaya
tidak boros—user dengan kota favorit sama tidak memicu fetch berulang.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from storage import JSONStorage
from texts import t
from weather_api import WeatherClient, DataSourceError, InvalidCityError
from weather_render import format_weather_message, compute_status_alerts, format_status_banner

logger = logging.getLogger("weatherbot.scheduler")
WIB = ZoneInfo("Asia/Jakarta")

EXTREME_ALERT_COOLDOWN = timedelta(hours=3)


async def _safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> bool:
    """Kirim pesan, tapi jangan sampai satu user gagal (blokir bot / chat
    dihapus) mematikan seluruh proses broadcast untuk user lain."""
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML", **kwargs)
        return True
    except TelegramForbiddenError:
        logger.info("User %s memblokir bot, skip pengiriman.", chat_id)
        return False
    except TelegramBadRequest as e:
        logger.warning("Gagal kirim ke %s: %s", chat_id, e)
        return False
    except Exception:
        logger.exception("Kegagalan tak terduga saat kirim pesan ke %s", chat_id)
        return False


async def daily_forecast_job(bot: Bot, storage: JSONStorage, client: WeatherClient) -> None:
    now_wib = datetime.now(WIB)
    today_str = now_wib.strftime("%Y-%m-%d")
    users = storage.users_with_daily_notify()

    due_users = [
        u for u in users
        if u["daily_notify"].get("hour") == now_wib.hour
        and u["daily_notify"].get("minute", 0) == now_wib.minute
        and u["daily_notify"].get("last_sent_date") != today_str
    ]
    if not due_users:
        return

    logger.info("daily_forecast_job: %d user due pada %02d:%02d WIB", len(due_users), now_wib.hour, now_wib.minute)

    # Kelompokkan per kota unik biar tidak fetch berulang untuk kota yang sama.
    cities_needed = {u["daily_notify"]["city"] for u in due_users if u["daily_notify"].get("city")}
    weather_cache = {}
    for city in cities_needed:
        try:
            weather_cache[city] = await asyncio.to_thread(client.get_weather, city)
        except (DataSourceError, InvalidCityError) as e:
            logger.warning("daily_forecast_job: gagal fetch %s: %s", city, e)
            weather_cache[city] = None

    for u in due_users:
        city = u["daily_notify"].get("city")
        weather_data = weather_cache.get(city)
        lang, unit = u.get("lang", "id"), u.get("unit", "c")
        if weather_data is None:
            continue  # tidak spam error ke user di notifikasi terjadwal, cukup skip

        text = f"{t(lang, 'push_daily_title', city=city)}\n\n{format_weather_message(lang, unit, city, weather_data, None)}"
        sent = await _safe_send(bot, u["user_id"], text)
        if sent:
            storage.update_user(u["user_id"], daily_notify={"last_sent_date": today_str})


async def quake_alert_job(bot: Bot, storage: JSONStorage, client: WeatherClient) -> None:
    latest = await asyncio.to_thread(client.get_earthquake_latest)
    if not latest:
        return

    quake_id = latest.get("DateTime") or f"{latest.get('Tanggal')}_{latest.get('Jam')}"
    last_seen = storage.get_meta("last_alerted_quake_id")
    if quake_id == last_seen:
        return  # bukan gempa baru, tidak perlu broadcast lagi

    storage.set_meta("last_alerted_quake_id", quake_id)
    if last_seen is None:
        # Run pertama kali sejak bot nyala: jangan langsung spam semua user
        # dengan gempa lama yang mungkin sudah terjadi sebelum bot start.
        logger.info("quake_alert_job: inisialisasi baseline gempa, belum broadcast.")
        return

    try:
        magnitude = float(latest.get("Magnitude", 0))
    except (ValueError, TypeError):
        magnitude = 0.0

    subscribers = storage.users_with_quake_alert()
    matching = [
        u for u in subscribers
        if magnitude >= u["quake_alert"].get("min_magnitude", 5.0)
        and (not u["quake_alert"].get("region_keyword")
             or u["quake_alert"]["region_keyword"].lower() in latest.get("Wilayah", "").lower())
    ]
    if not matching:
        return

    logger.info("quake_alert_job: gempa baru M%s di %s, broadcast ke %d user",
                magnitude, latest.get("Wilayah"), len(matching))

    for u in matching:
        lang = u.get("lang", "id")
        text = (
            f"{t(lang, 'push_quake_title')}\n\n"
            f"🌍 M{latest.get('Magnitude')} — {latest.get('Wilayah', 'N/A')}\n"
            f"📏 Kedalaman: {latest.get('Kedalaman', 'N/A')}\n"
            f"🕒 {latest.get('DateTime', '')}\n"
            f"⚠️ {latest.get('Potensi', 'N/A')}"
        )
        await _safe_send(bot, u["user_id"], text)


async def extreme_weather_job(bot: Bot, storage: JSONStorage, client: WeatherClient) -> None:
    subscribers = storage.users_with_extreme_alert()
    if not subscribers:
        return

    now = datetime.now(WIB)
    due = []
    for u in subscribers:
        last_sent_at = u["extreme_weather_alert"].get("last_sent_at")
        if last_sent_at:
            try:
                last_dt = datetime.fromisoformat(last_sent_at)
                if now - last_dt < EXTREME_ALERT_COOLDOWN:
                    continue
            except ValueError:
                pass
        due.append(u)
    if not due:
        return

    cities_needed = {u["extreme_weather_alert"]["city"] for u in due if u["extreme_weather_alert"].get("city")}
    data_cache = {}
    for city in cities_needed:
        try:
            weather_data = await asyncio.to_thread(client.get_weather, city)
            area = weather_data.get("nearest_area", [])
            lat = float(area[0].get("latitude", "0")) if area else 0.0
            lon = float(area[0].get("longitude", "0")) if area else 0.0
            aqi_data = await asyncio.to_thread(client.get_air_quality, lat, lon) if (lat and lon) else None
            data_cache[city] = (weather_data, aqi_data)
        except (DataSourceError, InvalidCityError) as e:
            logger.warning("extreme_weather_job: gagal fetch %s: %s", city, e)
            data_cache[city] = None

    warnings = await asyncio.to_thread(client.get_bmkg_warnings)

    for u in due:
        city = u["extreme_weather_alert"].get("city")
        cached = data_cache.get(city)
        if cached is None:
            continue
        weather_data, aqi_data = cached
        lang = u.get("lang", "id")
        alerts = compute_status_alerts(lang, weather_data, aqi_data, None, warnings)
        if not alerts:
            continue

        text = f"{t(lang, 'push_extreme_title', city=city)}\n\n{format_status_banner(lang, alerts)}"
        sent = await _safe_send(bot, u["user_id"], text)
        if sent:
            storage.update_user(u["user_id"], extreme_weather_alert={"last_sent_at": now.isoformat()})


def setup_scheduler(bot: Bot, storage: JSONStorage, client: WeatherClient, tick_seconds: int):
    """Bikin dan konfigurasi AsyncIOScheduler. Dipisah dari bot.py supaya
    gampang diuji / dimatikan sebagian job kalau perlu."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler(timezone=WIB)
    scheduler.add_job(daily_forecast_job, "interval", seconds=60,
                        args=[bot, storage, client], id="daily_forecast", max_instances=1)
    scheduler.add_job(quake_alert_job, "interval", seconds=tick_seconds,
                        args=[bot, storage, client], id="quake_alert", max_instances=1)
    scheduler.add_job(extreme_weather_job, "interval", seconds=max(tick_seconds, 1800),
                        args=[bot, storage, client], id="extreme_weather", max_instances=1)
    return scheduler
