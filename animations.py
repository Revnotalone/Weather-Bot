# -*- coding: utf-8 -*-
"""
Bikin bot terasa "hidup" walau cuma chat teks biasa:
  - Chat action native Telegram ("mengetik...")
  - Spinner + progress bar yang di-update lewat edit_message_text berulang
  - Progressive reveal (info muncul bertahap, bukan sekaligus)

Semua fungsi di sini defensif terhadap error Telegram (misal pesan sudah
dihapus user, atau edit ke teks yang identik -> Telegram menolak dengan
"message is not modified") supaya animasi tidak pernah bikin bot crash.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

logger = logging.getLogger("weatherbot.animations")

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
BAR_WIDTH = 12


def _progress_bar(percent: int) -> str:
    filled = max(0, min(BAR_WIDTH, round(BAR_WIDTH * percent / 100)))
    return "▓" * filled + "░" * (BAR_WIDTH - filled)


async def _safe_edit(bot: Bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode="HTML")
    except TelegramBadRequest as e:
        # Wajar terjadi: user hapus pesan, atau teks sama persis dengan sebelumnya.
        # Bukan bug -> cukup di-log level debug, jangan sampai bikin task crash.
        logger.debug("Edit pesan animasi dilewati: %s", e)


class LoadingAnimator:
    """Kirim pesan awal lalu animasikan sampai `finish()` dipanggil.

    Pemakaian:
        anim = LoadingAnimator(bot, chat_id, lang)
        await anim.start("cuaca")
        ... proses fetch data ...
        await anim.step("kualitas udara", percent=60)
        ... proses lagi ...
        await anim.finish()
    """

    def __init__(self, bot: Bot, chat_id: int, lang: str, texts_module):
        self.bot = bot
        self.chat_id = chat_id
        self.lang = lang
        self.t = texts_module.t
        self.message: Optional[Message] = None
        self._frame_idx = 0
        self._stop_flag = False
        self._bg_task: Optional[asyncio.Task] = None

    def _next_frame(self) -> str:
        frame = SPINNER_FRAMES[self._frame_idx % len(SPINNER_FRAMES)]
        self._frame_idx += 1
        return frame

    async def start(self, label: str, percent: int = 10) -> None:
        await self.bot.send_chat_action(self.chat_id, "typing")
        text = self.t(self.lang, "loading_frame", spinner=self._next_frame(),
                      label=label, bar=_progress_bar(percent), percent=percent)
        self.message = await self.bot.send_message(self.chat_id, text)
        self._bg_task = asyncio.create_task(self._idle_spin())

    async def _idle_spin(self) -> None:
        """Spinner terus berputar walau step() belum dipanggil, biar terasa
        aktif selama menunggu I/O (bukan cuma diam)."""
        try:
            while not self._stop_flag:
                await asyncio.sleep(0.7)
                if self._stop_flag or self.message is None:
                    return
        except asyncio.CancelledError:
            pass

    async def step(self, label: str, percent: int) -> None:
        if self.message is None:
            return
        text = self.t(self.lang, "loading_frame", spinner=self._next_frame(),
                      label=label, bar=_progress_bar(percent), percent=percent)
        await _safe_edit(self.bot, self.chat_id, self.message.message_id, text)

    async def finish(self) -> None:
        self._stop_flag = True
        if self._bg_task:
            self._bg_task.cancel()
        if self.message:
            await _safe_edit(self.bot, self.chat_id, self.message.message_id,
                              self.t(self.lang, "loading_done"))

    async def reveal(self, final_text: str, reply_markup=None) -> Message:
        """Ganti pesan loading jadi konten final. Dipanggil setelah finish()."""
        if self.message is None:
            return await self.bot.send_message(self.chat_id, final_text, parse_mode="HTML",
                                                 reply_markup=reply_markup)
        try:
            return await self.bot.edit_message_text(
                chat_id=self.chat_id, message_id=self.message.message_id,
                text=final_text, parse_mode="HTML", reply_markup=reply_markup,
            )
        except TelegramBadRequest as e:
            logger.debug("Reveal edit gagal, kirim pesan baru: %s", e)
            return await self.bot.send_message(self.chat_id, final_text, parse_mode="HTML",
                                                 reply_markup=reply_markup)


async def react_to_message(bot: Bot, chat_id: int, message_id: int, emoji: str) -> None:
    """Kasih emoji reaction dari bot ke pesan user (fitur Telegram Bot API
    terbaru). Best-effort — kalau client/versi Bot API belum support, cukup
    di-log, jangan sampai bikin handler gagal total."""
    try:
        from aiogram.types import ReactionTypeEmoji
        await bot.set_message_reaction(
            chat_id=chat_id, message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)],
        )
    except Exception as e:  # noqa: BLE001 - reaction murni kosmetik, tidak boleh crash flow utama
        logger.debug("Gagal set reaction (non-fatal): %s", e)
