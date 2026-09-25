# -*- coding: utf-8 -*-
"""
Inline mode: ketik `@namabot jakarta` di chat manapun (bahkan chat lain,
bukan cuma chat dengan bot) untuk hasil cuaca instan. Juga dipakai oleh
tombol "📤 Bagikan" di kartu cuaca (switch_inline_query).
"""
from __future__ import annotations

import asyncio
import logging
from hashlib import md5

from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from storage import JSONStorage
from weather_api import WeatherClient, DataSourceError, InvalidCityError
from weather_render import format_weather_message

logger = logging.getLogger("weatherbot.handlers.inline")
router = Router(name="inline_mode")


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery, storage: JSONStorage, client: WeatherClient):
    query = inline_query.query.strip()
    user = storage.get_user(inline_query.from_user.id)
    lang, unit = user.get("lang", "id"), user.get("unit", "c")

    if not query:
        hint = InlineQueryResultArticle(
            id="hint",
            title="🌤️ Ketik nama kota..." if lang == "id" else "🌤️ Type a city name...",
            description="Contoh: jakarta, bandung, surabaya" if lang == "id" else "e.g. jakarta, london, tokyo",
            input_message_content=InputTextMessageContent(
                message_text="🌤️ /start — cek cuaca kota favoritmu lewat WeatherBot!"
            ),
        )
        await inline_query.answer([hint], cache_time=60, is_personal=True)
        return

    try:
        weather_data = await asyncio.to_thread(client.get_weather, query)
        text = format_weather_message(lang, unit, query, weather_data, None)
        result_id = md5(query.lower().encode()).hexdigest()[:16]
        result = InlineQueryResultArticle(
            id=result_id,
            title=f"🌤️ Cuaca {query}" if lang == "id" else f"🌤️ Weather in {query}",
            description="Tap untuk kirim kartu cuaca ini" if lang == "id" else "Tap to send this weather card",
            input_message_content=InputTextMessageContent(message_text=text, parse_mode="HTML"),
        )
        await inline_query.answer([result], cache_time=120, is_personal=False)
    except (DataSourceError, InvalidCityError) as e:
        logger.info("Inline query gagal untuk '%s': %s", query, e)
        error_result = InlineQueryResultArticle(
            id="notfound",
            title="❌ Kota tidak ditemukan" if lang == "id" else "❌ City not found",
            description=query,
            input_message_content=InputTextMessageContent(message_text=f"❌ '{query}' — data tidak tersedia."),
        )
        await inline_query.answer([error_result], cache_time=10, is_personal=True)
    except Exception:
        logger.exception("Kegagalan tak terduga di inline query untuk '%s'", query)
        await inline_query.answer([], cache_time=5)
