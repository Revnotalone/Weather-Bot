# -*- coding: utf-8 -*-
"""
Fungsi MURNI (tanpa I/O, tanpa aiogram) yang mengubah data mentah jadi teks
pesan HTML siap kirim. Dipisah dari handler supaya:
  - Bisa dites tanpa perlu mock Telegram sama sekali.
  - Dipakai ulang oleh handler interaktif MAUPUN scheduler (push notifikasi)
    tanpa duplikasi logika format.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from texts import t
from weather_api import extract_value, format_temp, aqi_category, weather_icon


def format_weather_message(lang: str, unit: str, city: str,
                             weather_data: Dict[str, Any],
                             aqi_data: Optional[Dict[str, Any]]) -> str:
    current = weather_data.get("current_condition", [{}])[0]
    desc = extract_value(current.get("weatherDesc", "N/A"))
    icon = weather_icon(desc)

    lines = [t(lang, "weather_card_title", icon=icon, city=city)]
    lines.append(f"<i>{desc}</i>")
    lines.append("")
    lines.append(t(lang, "weather_temp",
                    temp=format_temp(extract_value(current.get("temp_C", "N/A")), unit),
                    feels=format_temp(extract_value(current.get("FeelsLikeC", "N/A")), unit)))
    lines.append(t(lang, "weather_humidity", humidity=extract_value(current.get("humidity", "N/A"))))
    lines.append(t(lang, "weather_wind",
                    speed=extract_value(current.get("windspeedKmph", "N/A")),
                    dir=extract_value(current.get("winddir16Point", ""))))
    lines.append(t(lang, "weather_uv", uv=extract_value(current.get("uvIndex", "N/A"))))
    lines.append(t(lang, "weather_visibility", vis=extract_value(current.get("visibility", "N/A"))))

    if aqi_data:
        us_aqi = aqi_data.get("us_aqi", "N/A")
        label, aqi_icon, advice = aqi_category(us_aqi)
        lines.append("")
        lines.append(t(lang, "aqi_line", icon=aqi_icon, label=label, aqi=us_aqi))
        lines.append(t(lang, "aqi_advice", advice=advice))

    text = "\n".join(lines)
    if weather_data.get("_stale"):
        text += t(lang, "weather_stale_note")
    return text


def format_forecast_message(lang: str, unit: str, city: str, weather_list: List[Dict[str, Any]]) -> str:
    lines = [t(lang, "btn_forecast") + f" — <b>{city}</b>\n"]
    for day in weather_list[:3]:
        date = day.get("date", "N/A")
        max_t = format_temp(day.get("maxtempC", "?"), unit)
        min_t = format_temp(day.get("mintempC", "?"), unit)
        hourly = day.get("hourly", [])

        def desc_at(target_time: str) -> str:
            for h in hourly:
                if h.get("time") == target_time:
                    return extract_value(h.get("weatherDesc", ""))
            return extract_value(hourly[0].get("weatherDesc", "")) if hourly else "N/A"

        rain_vals = [int(h.get("chanceofrain", 0)) for h in hourly] if hourly else [0]
        icon = weather_icon(desc_at("1200"))
        lines.append(
            f"{icon} <b>{date}</b> — {min_t} … {max_t}\n"
            f"   🌅 {desc_at('600')}  ☀️ {desc_at('1200')}  🌙 {desc_at('1800')}\n"
            f"   🌧️ Peluang hujan tertinggi: {max(rain_vals)}%"
        )
    return "\n\n".join(lines)


def format_earthquake_detail_message(lang: str, eq_latest: Optional[Dict[str, Any]],
                                       eq_list: List[Dict[str, Any]],
                                       eq_felt: List[Dict[str, Any]]) -> str:
    lines = [f"🌍 <b>{t(lang, 'btn_earthquake_more')}</b>\n"]
    if eq_latest:
        lines.append(
            "<b>Terbaru:</b>\n"
            f"M{eq_latest.get('Magnitude', '?')} — {eq_latest.get('Wilayah', 'N/A')}\n"
            f"🕒 {eq_latest.get('DateTime', '')}  📏 {eq_latest.get('Kedalaman', '?')}\n"
            f"⚠️ {eq_latest.get('Potensi', 'N/A')}"
        )
    else:
        lines.append(t(lang, "eq_none"))

    if eq_list:
        lines.append("\n<b>Gempa M5+ Terkini:</b>")
        for q in eq_list:
            lines.append(f"• M{q.get('Magnitude', '?')} — {q.get('Wilayah', 'N/A')} ({q.get('Jam', '')})")

    if eq_felt:
        lines.append("\n<b>Dirasakan Warga:</b>")
        for q in eq_felt:
            lines.append(f"• M{q.get('Magnitude', '?')} — {q.get('Wilayah', 'N/A')} ({q.get('Jam', '')})")

    return "\n".join(lines)


def compute_status_alerts(lang: str, weather_data: Optional[Dict[str, Any]],
                            aqi_data: Optional[Dict[str, Any]],
                            eq_data: Optional[Dict[str, Any]],
                            warnings: List[Dict[str, str]]) -> List[Tuple[str, str]]:
    alerts: List[Tuple[str, str]] = []

    if weather_data and weather_data.get("current_condition"):
        current = weather_data["current_condition"][0]
        try:
            temp_c = float(extract_value(current.get("temp_C", "0")))
            if temp_c >= 35:
                alerts.append(("🌡️ Suhu ekstrem tinggi", f"{temp_c:.0f}°C — perbanyak minum air, hindari aktivitas berat siang hari."))
        except ValueError:
            pass
        try:
            uv = float(extract_value(current.get("uvIndex", "0")))
            if uv >= 8:
                alerts.append(("☀️ Indeks UV sangat tinggi", f"UV {uv:.0f} — gunakan tabir surya & topi/payung."))
        except ValueError:
            pass

    if aqi_data:
        us_aqi = aqi_data.get("us_aqi")
        if us_aqi is not None:
            label, _, advice = aqi_category(us_aqi)
            if label in ("Tidak Sehat", "Sangat Tidak Sehat", "Berbahaya"):
                alerts.append((f"🌫️ Kualitas udara: {label} (AQI {us_aqi})", advice))

    if eq_data:
        try:
            mag = float(eq_data.get("Magnitude", 0))
            if mag >= 5.0:
                alerts.append((f"🌍 Gempa signifikan M{mag}", eq_data.get("Wilayah", "Lokasi tidak diketahui")))
        except (ValueError, TypeError):
            pass

    for w in warnings[:3]:
        alerts.append((f"⚠️ Peringatan BMKG: {w['event']}", w["area"]))

    return alerts


def format_status_banner(lang: str, alerts: List[Tuple[str, str]]) -> str:
    if not alerts:
        return t(lang, "status_alert_none")
    lines = [t(lang, "status_alert_title")]
    for title, detail in alerts:
        lines.append(f"\n<b>{title}</b>\n{detail}")
    return "\n".join(lines)
