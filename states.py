# -*- coding: utf-8 -*-
"""State machine states untuk flow yang butuh menunggu input teks user."""
from aiogram.fsm.state import State, StatesGroup


class WeatherFlow(StatesGroup):
    waiting_city = State()  # user diminta ketik nama kota buat dicek


class NotifFlow(StatesGroup):
    waiting_daily_city_manual = State()  # user ketik manual nama kota utk ramalan harian
