# -*- coding: utf-8 -*-
"""
Render grafik suhu & peluang hujan per jam jadi PNG (dikirim sebagai foto).
Dibuat gelap/modern biar matching tema dark mode Telegram.
"""
from __future__ import annotations

import io
from typing import List, Dict, Any

import matplotlib
matplotlib.use("Agg")  # headless, tidak butuh display
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

BG_COLOR = "#17212b"       # mirip warna chat Telegram dark
GRID_COLOR = "#2b3b4d"
TEMP_COLOR = "#ff9f43"
RAIN_COLOR = "#54a0ff"
TEXT_COLOR = "#e8eef5"


def render_hourly_chart(hourly: List[Dict[str, Any]], city: str, unit: str = "c") -> bytes:
    """Generate PNG chart bytes. Aman dipanggil dengan data kosong (raise ValueError)."""
    if not hourly:
        raise ValueError("Data per jam kosong, tidak bisa membuat grafik.")

    times, temps, rains = [], [], []
    for h in hourly:
        raw_time = str(h.get("time", "0"))
        hour_num = int(raw_time) // 100 if len(raw_time) > 2 else int(raw_time or 0)
        times.append(f"{hour_num:02d}")
        temp_c = float(h.get("tempC", 0))
        temps.append(temp_c * 9 / 5 + 32 if unit == "f" else temp_c)
        rains.append(float(h.get("chanceofrain", 0)))

    fig, ax1 = plt.subplots(figsize=(9, 4.5), dpi=150)
    fig.patch.set_facecolor(BG_COLOR)
    ax1.set_facecolor(BG_COLOR)

    x = range(len(times))
    ax1.plot(x, temps, color=TEMP_COLOR, linewidth=2.5, marker="o", markersize=4,
              label=f"Suhu ({'°F' if unit == 'f' else '°C'})")
    ax1.fill_between(x, temps, min(temps) - 2, color=TEMP_COLOR, alpha=0.12)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(times, color=TEXT_COLOR, fontsize=9)
    ax1.tick_params(axis="y", colors=TEXT_COLOR)
    ax1.set_ylabel("Suhu", color=TEMP_COLOR, fontsize=10)
    ax1.grid(True, color=GRID_COLOR, linewidth=0.7, alpha=0.6)
    for spine in ax1.spines.values():
        spine.set_color(GRID_COLOR)

    ax2 = ax1.twinx()
    ax2.bar(x, rains, color=RAIN_COLOR, alpha=0.35, width=0.5, label="Peluang Hujan (%)")
    ax2.set_ylim(0, 100)
    ax2.tick_params(axis="y", colors=TEXT_COLOR)
    ax2.set_ylabel("Hujan (%)", color=RAIN_COLOR, fontsize=10)
    for spine in ax2.spines.values():
        spine.set_visible(False)

    fig.suptitle(f"Ramalan Per Jam — {city}", color=TEXT_COLOR, fontsize=13, fontweight="bold")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    legend = ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left",
                          facecolor=BG_COLOR, edgecolor=GRID_COLOR, fontsize=8, framealpha=0.9)
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=BG_COLOR)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
