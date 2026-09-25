# -*- coding: utf-8 -*-
"""Kumpulkan semua router jadi satu list, dipakai oleh bot.py."""
from aiogram import Router

from handlers import start, weather, favorites, notifications, settings, export, inline_mode


def get_all_routers() -> list[Router]:
    # Urutan penting: router paling spesifik duluan. `weather.router` punya
    # catch-all handler teks (StateFilter(None)) jadi HARUS di urutan
    # terakhir supaya router lain (yang juga punya handler teks via FSM
    # state spesifik seperti notifications) sempat dicek lebih dulu.
    return [
        start.router,
        favorites.router,
        notifications.router,
        settings.router,
        export.router,
        inline_mode.router,
        weather.router,
    ]
