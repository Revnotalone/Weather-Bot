#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry point WeatherBot. Jalankan dengan:

    python3 bot.py

Pastikan sudah:
  1. pip install -r requirements.txt
  2. Salin .env.example jadi .env, isi BOT_TOKEN dari @BotFather
"""
from __future__ import annotations

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from handlers import get_all_routers
from scheduler import setup_scheduler
from storage import JSONStorage
from weather_api import WeatherClient

logger = logging.getLogger("weatherbot")


def setup_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("weatherbot")
    root.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        config.LOG_DIR / "bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Redam log super cerewet dari library HTTP pihak ketiga.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def main() -> None:
    setup_logging()
    try:
        config.validate()
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    data_storage = JSONStorage(config.DATA_DIR / "users.json")
    weather_client = WeatherClient(
        config.DATA_DIR / "cache", cache_ttl=config.CACHE_TTL_SECONDS, use_cache=True
    )

    for router in get_all_routers():
        dp.include_router(router)

    scheduler = setup_scheduler(bot, data_storage, weather_client, config.SCHEDULER_TICK_SECONDS)
    scheduler.start()
    logger.info("Scheduler notifikasi (harian/gempa/cuaca ekstrem) berjalan.")

    me = await bot.get_me()
    logger.info("WeatherBot @%s siap. Mulai polling...", me.username)

    try:
        await dp.start_polling(bot, storage=data_storage, client=weather_client)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot berhenti dengan bersih.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Dihentikan oleh pengguna (Ctrl+C).")
