# -*- coding: utf-8 -*-
"""
Semua string yang tampil ke user, dipisah dari logika supaya:
  1. Gampang diaudit typo/tone tanpa buka kode handler.
  2. Gampang nambah bahasa baru — tinggal tambah satu dict baru di TEXTS.
  3. Konsisten: tidak ada string user-facing yang nyasar ditulis inline di handler.
"""
from __future__ import annotations

from typing import Any

TEXTS: dict[str, dict[str, str]] = {
    "id": {
        "welcome": (
            "👋 <b>Halo, {name}!</b>\n\n"
            "Aku <b>WeatherBot</b> — asisten cuaca, kualitas udara, dan gempa "
            "bumi Indonesia real-time, langsung dari BMKG & sumber terpercaya "
            "lainnya.\n\n"
            "Pilih menu di bawah, atau ketik nama kota langsung ✍️"
        ),
        "main_menu_title": "🏠 <b>Menu Utama</b>\nMau lihat apa hari ini?",
        "btn_check_weather": "🌤️ Cek Cuaca",
        "btn_favorites": "⭐ Kota Favorit",
        "btn_notifications": "🔔 Notifikasi",
        "btn_settings": "⚙️ Pengaturan",
        "btn_help": "❓ Bantuan",
        "btn_back": "◀️ Kembali",
        "btn_home": "🏠 Menu Utama",
        "btn_refresh": "🔄 Refresh",
        "btn_share": "📤 Bagikan",
        "btn_add_favorite": "⭐ Simpan Favorit",
        "btn_remove_favorite": "🗑️ Hapus dari Favorit",
        "btn_export": "📄 Ekspor Laporan",
        "btn_hourly_chart": "📊 Grafik Per Jam",
        "btn_forecast": "📅 Ramalan 3 Hari",
        "btn_earthquake_more": "🌍 Info Gempa Lengkap",
        "ask_city": "🔍 Ketik nama kota yang mau kamu cek cuacanya:",
        "loading_frame": "{spinner} Mengambil data {label}... {bar} {percent}%",
        "loading_done": "✅ Data lengkap!",
        "weather_stale_note": "\n\n⚠️ <i>Data dari cache (koneksi ke sumber sedang bermasalah)</i>",
        "weather_card_title": "{icon} <b>Cuaca {city}</b>",
        "weather_temp": "🌡️ Suhu: <b>{temp}</b> (terasa {feels})",
        "weather_humidity": "💧 Kelembapan: {humidity}%",
        "weather_wind": "🍃 Angin: {speed} km/h {dir}",
        "weather_uv": "☀️ Indeks UV: {uv}",
        "weather_visibility": "👁️ Visibilitas: {vis} km",
        "aqi_line": "{icon} Kualitas Udara: <b>{label}</b> (AQI {aqi})",
        "aqi_advice": "💡 {advice}",
        "eq_none": "🌍 Tidak ada data gempa signifikan terbaru.",
        "eq_line": "🌍 Gempa terakhir: M{mag} — {wilayah} ({depth})",
        "warn_none": "✅ Tidak ada peringatan dini cuaca ekstrem aktif.",
        "warn_line": "⚠️ Peringatan BMKG: {event} di {area}",
        "status_alert_title": "🚨 <b>STATUS: WASPADA</b>",
        "status_alert_none": "✅ Kondisi normal, tidak ada peringatan khusus.",
        "fav_empty": "⭐ Kamu belum punya kota favorit.\nTambahkan lewat menu cek cuaca!",
        "fav_title": "⭐ <b>Kota Favorit Kamu</b>\nTap untuk cek cuaca cepat:",
        "fav_added": "✅ <b>{city}</b> ditambahkan ke favorit!",
        "fav_removed": "🗑️ <b>{city}</b> dihapus dari favorit.",
        "fav_already": "ℹ️ <b>{city}</b> sudah ada di favorit kamu.",
        "notif_title": "🔔 <b>Pengaturan Notifikasi</b>",
        "notif_daily_label": "Ramalan Harian",
        "notif_quake_label": "Alert Gempa",
        "notif_extreme_label": "Alert Cuaca Ekstrem",
        "notif_daily_status": "📅 Ramalan Harian: {status}",
        "notif_quake_status": "🌍 Alert Gempa (M≥{mag}): {status}",
        "notif_extreme_status": "🚨 Alert Cuaca Ekstrem: {status}",
        "status_on": "✅ Aktif",
        "status_off": "⭕ Nonaktif",
        "notif_daily_set_city": "Pilih kota untuk ramalan harian:",
        "notif_daily_set_time": "Pilih jam pengiriman ramalan harian (WIB):",
        "notif_daily_saved": "✅ Ramalan harian diaktifkan untuk <b>{city}</b> jam <b>{hour:02d}:{minute:02d}</b> WIB.",
        "notif_daily_off": "⭕ Ramalan harian dinonaktifkan.",
        "notif_quake_on": "✅ Alert gempa M≥{mag} diaktifkan.",
        "notif_quake_off": "⭕ Alert gempa dinonaktifkan.",
        "notif_extreme_on": "✅ Alert cuaca ekstrem untuk <b>{city}</b> diaktifkan.",
        "notif_extreme_off": "⭕ Alert cuaca ekstrem dinonaktifkan.",
        "push_daily_title": "☀️ <b>Ramalan Cuaca Hari Ini — {city}</b>",
        "push_quake_title": "🚨 <b>GEMPA BARU TERDETEKSI</b>",
        "push_extreme_title": "🚨 <b>PERINGATAN CUACA EKSTREM — {city}</b>",
        "settings_title": "⚙️ <b>Pengaturan</b>",
        "settings_unit": "🌡️ Satuan Suhu: <b>{unit}</b>",
        "settings_lang": "🌐 Bahasa: <b>{lang_label}</b>",
        "settings_unit_changed": "✅ Satuan suhu diganti ke <b>{unit}</b>.",
        "settings_lang_changed": "✅ Bahasa diganti ke <b>{lang_label}</b>.",
        "help_text": (
            "❓ <b>Cara Pakai WeatherBot</b>\n\n"
            "• Ketik nama kota langsung, atau pakai menu 🌤️ Cek Cuaca\n"
            "• Simpan kota favorit ⭐ biar cek cepat tiap hari\n"
            "• Aktifkan 🔔 Notifikasi buat ramalan otomatis tiap pagi & alert gempa\n"
            "• Kirim <b>lokasi</b> 📍 (attach → Location) buat cuaca di posisi kamu\n"
            "• Ketik <code>@{bot_username} nama_kota</code> di chat manapun untuk hasil instan\n\n"
            "Sumber data: wttr.in, Open-Meteo, BMKG."
        ),
        "invalid_city": "❌ {error}",
        "city_not_found": "❌ Kota '<b>{city}</b>' tidak ditemukan atau data sedang tidak tersedia.\nCoba nama lain atau cek ejaan.",
        "generic_error": "❌ Ada yang salah. Sudah tercatat di log, coba lagi sebentar lagi ya.",
        "share_location_prompt": "📍 Kirim lokasi kamu untuk cek cuaca otomatis di posisi kamu.",
        "export_ready": "📄 Laporan cuaca {city} siap!",
        "exporting": "📄 Menyiapkan laporan...",
    },
    "en": {
        "welcome": (
            "👋 <b>Hi, {name}!</b>\n\n"
            "I'm <b>WeatherBot</b> — real-time weather, air quality, and "
            "earthquake info for Indonesia straight from BMKG and trusted "
            "sources.\n\nPick a menu below, or just type a city name ✍️"
        ),
        "main_menu_title": "🏠 <b>Main Menu</b>\nWhat do you want to check today?",
        "btn_check_weather": "🌤️ Check Weather",
        "btn_favorites": "⭐ Favorite Cities",
        "btn_notifications": "🔔 Notifications",
        "btn_settings": "⚙️ Settings",
        "btn_help": "❓ Help",
        "btn_back": "◀️ Back",
        "btn_home": "🏠 Main Menu",
        "btn_refresh": "🔄 Refresh",
        "btn_share": "📤 Share",
        "btn_add_favorite": "⭐ Save Favorite",
        "btn_remove_favorite": "🗑️ Remove Favorite",
        "btn_export": "📄 Export Report",
        "btn_hourly_chart": "📊 Hourly Chart",
        "btn_forecast": "📅 3-Day Forecast",
        "btn_earthquake_more": "🌍 Full Earthquake Info",
        "ask_city": "🔍 Type the city name you want to check:",
        "loading_frame": "{spinner} Fetching {label} data... {bar} {percent}%",
        "loading_done": "✅ Data ready!",
        "weather_stale_note": "\n\n⚠️ <i>Cached data (source connection having issues)</i>",
        "weather_card_title": "{icon} <b>Weather in {city}</b>",
        "weather_temp": "🌡️ Temp: <b>{temp}</b> (feels like {feels})",
        "weather_humidity": "💧 Humidity: {humidity}%",
        "weather_wind": "🍃 Wind: {speed} km/h {dir}",
        "weather_uv": "☀️ UV Index: {uv}",
        "weather_visibility": "👁️ Visibility: {vis} km",
        "aqi_line": "{icon} Air Quality: <b>{label}</b> (AQI {aqi})",
        "aqi_advice": "💡 {advice}",
        "eq_none": "🌍 No significant recent earthquake data.",
        "eq_line": "🌍 Latest quake: M{mag} — {wilayah} ({depth})",
        "warn_none": "✅ No active severe weather warnings.",
        "warn_line": "⚠️ BMKG Warning: {event} in {area}",
        "status_alert_title": "🚨 <b>STATUS: ALERT</b>",
        "status_alert_none": "✅ Normal conditions, no special alerts.",
        "fav_empty": "⭐ You don't have any favorite cities yet.\nAdd one from the weather check menu!",
        "fav_title": "⭐ <b>Your Favorite Cities</b>\nTap for a quick check:",
        "fav_added": "✅ <b>{city}</b> added to favorites!",
        "fav_removed": "🗑️ <b>{city}</b> removed from favorites.",
        "fav_already": "ℹ️ <b>{city}</b> is already in your favorites.",
        "notif_title": "🔔 <b>Notification Settings</b>",
        "notif_daily_label": "Daily Forecast",
        "notif_quake_label": "Earthquake Alert",
        "notif_extreme_label": "Extreme Weather Alert",
        "notif_daily_status": "📅 Daily Forecast: {status}",
        "notif_quake_status": "🌍 Earthquake Alert (M≥{mag}): {status}",
        "notif_extreme_status": "🚨 Extreme Weather Alert: {status}",
        "status_on": "✅ On",
        "status_off": "⭕ Off",
        "notif_daily_set_city": "Choose a city for the daily forecast:",
        "notif_daily_set_time": "Choose the daily forecast delivery time (WIB):",
        "notif_daily_saved": "✅ Daily forecast enabled for <b>{city}</b> at <b>{hour:02d}:{minute:02d}</b> WIB.",
        "notif_daily_off": "⭕ Daily forecast disabled.",
        "notif_quake_on": "✅ Earthquake alert M≥{mag} enabled.",
        "notif_quake_off": "⭕ Earthquake alert disabled.",
        "notif_extreme_on": "✅ Extreme weather alert for <b>{city}</b> enabled.",
        "notif_extreme_off": "⭕ Extreme weather alert disabled.",
        "push_daily_title": "☀️ <b>Today's Forecast — {city}</b>",
        "push_quake_title": "🚨 <b>NEW EARTHQUAKE DETECTED</b>",
        "push_extreme_title": "🚨 <b>EXTREME WEATHER WARNING — {city}</b>",
        "settings_title": "⚙️ <b>Settings</b>",
        "settings_unit": "🌡️ Temperature Unit: <b>{unit}</b>",
        "settings_lang": "🌐 Language: <b>{lang_label}</b>",
        "settings_unit_changed": "✅ Temperature unit changed to <b>{unit}</b>.",
        "settings_lang_changed": "✅ Language changed to <b>{lang_label}</b>.",
        "help_text": (
            "❓ <b>How to use WeatherBot</b>\n\n"
            "• Type a city name directly, or use 🌤️ Check Weather\n"
            "• Save favorite cities ⭐ for quick daily checks\n"
            "• Enable 🔔 Notifications for daily forecasts & earthquake alerts\n"
            "• Send your <b>location</b> 📍 for weather at your position\n"
            "• Type <code>@{bot_username} city_name</code> in any chat for instant results\n\n"
            "Data sources: wttr.in, Open-Meteo, BMKG."
        ),
        "invalid_city": "❌ {error}",
        "city_not_found": "❌ City '<b>{city}</b>' not found or data unavailable.\nTry another name or check spelling.",
        "generic_error": "❌ Something went wrong. It's logged — please try again shortly.",
        "share_location_prompt": "📍 Send your location to check weather at your position.",
        "export_ready": "📄 Weather report for {city} is ready!",
        "exporting": "📄 Preparing report...",
    },
}


def t(lang: str, key: str, **kwargs: Any) -> str:
    lang_dict = TEXTS.get(lang, TEXTS["id"])
    template = lang_dict.get(key) or TEXTS["id"].get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
