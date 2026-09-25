# -*- coding: utf-8 -*-
"""
Konfigurasi bot — diisi LANGSUNG di sini (tanpa file .env / environment
variable), sesuai permintaan.

⚠️ Karena token ditaruh langsung di source code: JANGAN upload/commit file
ini ke repo publik (GitHub publik, dsb) dengan token asli masih terisi.
Kalau project ini nanti mau di-share/di-publish, kosongkan lagi BOT_TOKEN
di bawah sebelum di-upload.
"""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ============================================================
# WAJIB DIISI: token bot dari @BotFather di Telegram
# ============================================================
BOT_TOKEN = "PASTE-DISINI"

# ============================================================
# Opsional — boleh dibiarkan default
# ============================================================
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DEFAULT_LANG = "id"
DEFAULT_UNIT = "c"
ADMIN_IDS: set[int] = set()  # contoh: {123456789, 987654321}

# Interval polling scheduler (detik) — seberapa sering cek jadwal notifikasi
# harian & alert gempa/cuaca ekstrem.
SCHEDULER_TICK_SECONDS = 60

# Cache HTTP (detik) — biar tidak hammer API kalau banyak user cek kota sama.
CACHE_TTL_SECONDS = 300

# Ambang magnitudo default untuk alert gempa otomatis.
DEFAULT_QUAKE_MIN_MAGNITUDE = 5.0


def validate() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "ISI_TOKEN_BOT_DI_SINI":
        raise RuntimeError(
            "BOT_TOKEN belum diisi. Buka config.py, ganti nilai BOT_TOKEN "
            "dengan token asli dari @BotFather."
        )
