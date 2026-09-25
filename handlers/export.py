# -*- coding: utf-8 -*-
"""Ekspor laporan cuaca kota aktif jadi file .txt yang dikirim sebagai dokumen."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile

from storage import JSONStorage
from texts import t
from weather_api import WeatherClient, DataSourceError, InvalidCityError
from weather_render import (
    format_weather_message, format_forecast_message,
    format_earthquake_detail_message, compute_status_alerts, format_status_banner,
)

logger = logging.getLogger("weatherbot.handlers.export")
router = Router(name="export")


def _strip_html(text: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", text)


@router.callback_query(F.data == "wx:export")
async def export_report(callback: CallbackQuery, storage: JSONStorage, client: WeatherClient):
    user = storage.get_user(callback.from_user.id)
    lang, unit = user.get("lang", "id"), user.get("unit", "c")
    city = user.get("last_city")
    if not city:
        await callback.answer()
        return

    await callback.answer(t(lang, "exporting").replace("<b>", "").replace("</b>", ""))
    await callback.bot.send_chat_action(callback.message.chat.id, "upload_document")

    try:
        weather_data = await asyncio.to_thread(client.get_weather, city)
        area = weather_data.get("nearest_area", [])
        lat = float(area[0].get("latitude", "0")) if area else 0.0
        lon = float(area[0].get("longitude", "0")) if area else 0.0
        aqi_data = await asyncio.to_thread(client.get_air_quality, lat, lon) if (lat and lon) else None
        eq_latest = await asyncio.to_thread(client.get_earthquake_latest)
        warnings = await asyncio.to_thread(client.get_bmkg_warnings)
    except (DataSourceError, InvalidCityError):
        await callback.bot.send_message(callback.message.chat.id, t(lang, "city_not_found", city=city))
        return
    except Exception:
        logger.exception("Gagal ekspor laporan untuk kota=%s", city)
        await callback.bot.send_message(callback.message.chat.id, t(lang, "generic_error"))
        return

    alerts = compute_status_alerts(lang, weather_data, aqi_data, eq_latest, warnings)
    sections = [
        "=" * 50,
        f"LAPORAN CUACA — {city.upper()}",
        f"Dibuat: {datetime.now().strftime('%Y-%m-%d %H:%M')} WIB",
        "=" * 50,
        "",
        _strip_html(format_status_banner(lang, alerts)),
        "",
        _strip_html(format_weather_message(lang, unit, city, weather_data, aqi_data)),
        "",
        _strip_html(format_forecast_message(lang, unit, city, weather_data.get("weather", []))),
        "",
        _strip_html(format_earthquake_detail_message(lang, eq_latest, [], [])),
        "",
        "-- Dihasilkan otomatis oleh WeatherBot --",
    ]
    content = "\n".join(sections)
    file_bytes = content.encode("utf-8")
    filename = f"laporan_{city.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    document = BufferedInputFile(file_bytes, filename=filename)
    await callback.bot.send_document(
        callback.message.chat.id, document,
        caption=t(lang, "export_ready", city=city).replace("<b>", "").replace("</b>", ""),
    )
