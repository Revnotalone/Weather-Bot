# -*- coding: utf-8 -*-
"""
Penyimpanan data user TANPA database server — hanya file JSON di disk.

Kenapa aman dipakai walau "cuma file JSON"?
  - Semua baca/tulis dikunci dengan threading.Lock (satu proses bot, aman
    dari race condition antar handler yang jalan bersamaan).
  - Penulisan bersifat ATOMIC: ditulis dulu ke file sementara lalu
    os.replace() ke file asli, jadi kalau bot crash di tengah proses
    menyimpan, file data lama tidak akan rusak/corrupt.
  - Backup otomatis: sebelum overwrite, salinan sebelumnya disimpan sebagai
    data.json.bak.

Cocok untuk skala personal/menengah (ratusan-ribuan user aktif). Kalau nanti
butuh scale jauh lebih besar / query kompleks, struktur DEFAULT_USER di bawah
bisa dipetakan langsung ke tabel SQL tanpa banyak perubahan pada kode caller.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("weatherbot.storage")

DEFAULT_USER: Dict[str, Any] = {
    "lang": "id",
    "unit": "c",
    "favorites": [],          # list[str] nama kota
    "last_city": None,        # str | None
    "daily_notify": {
        "enabled": False,
        "hour": 6,
        "minute": 0,
        "city": None,          # None -> pakai last_city saat kirim
    },
    "quake_alert": {
        "enabled": False,
        "min_magnitude": 5.0,
        "region_keyword": None,  # filter substring wilayah, None = semua wilayah
    },
    "extreme_weather_alert": {
        "enabled": False,
        "city": None,           # None -> pakai last_city
    },
    "created_at": None,
    "updated_at": None,
}


class JSONStorage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {"users": {}, "_meta": {"last_alerted_quake_id": None}}
        self._load()

    # -------------------------------------------------------------- I/O --
    def _load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._save_unlocked()
                return
            try:
                raw = self.path.read_text(encoding="utf-8")
                self._data = json.loads(raw)
                self._data.setdefault("users", {})
                self._data.setdefault("_meta", {"last_alerted_quake_id": None})
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Gagal baca %s (%s). Mencoba file backup .bak", self.path, e)
                backup = self.path.with_suffix(".json.bak")
                if backup.exists():
                    try:
                        self._data = json.loads(backup.read_text(encoding="utf-8"))
                        logger.info("Berhasil pulih dari backup.")
                        return
                    except (json.JSONDecodeError, OSError) as e2:
                        logger.error("Backup juga rusak (%s). Mulai dari data kosong.", e2)
                self._data = {"users": {}, "_meta": {"last_alerted_quake_id": None}}

    def _save_unlocked(self) -> None:
        tmp_path = self.path.with_suffix(".json.tmp")
        try:
            if self.path.exists():
                backup = self.path.with_suffix(".json.bak")
                backup.write_bytes(self.path.read_bytes())
            tmp_path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp_path, self.path)
        except OSError as e:
            logger.error("Gagal menyimpan storage ke %s: %s", self.path, e)
            raise

    def save(self) -> None:
        with self._lock:
            self._save_unlocked()

    # ------------------------------------------------------------ USERS --
    def get_user(self, user_id: int) -> Dict[str, Any]:
        with self._lock:
            key = str(user_id)
            if key not in self._data["users"]:
                user = json.loads(json.dumps(DEFAULT_USER))  # deep copy
                now = time.time()
                user["created_at"] = now
                user["updated_at"] = now
                self._data["users"][key] = user
                self._save_unlocked()
            return json.loads(json.dumps(self._data["users"][key]))  # return copy

    def update_user(self, user_id: int, **fields: Any) -> Dict[str, Any]:
        with self._lock:
            key = str(user_id)
            user = self._data["users"].get(key)
            if user is None:
                user = json.loads(json.dumps(DEFAULT_USER))
                user["created_at"] = time.time()
            for k, v in fields.items():
                if isinstance(v, dict) and isinstance(user.get(k), dict):
                    user[k].update(v)
                else:
                    user[k] = v
            user["updated_at"] = time.time()
            self._data["users"][key] = user
            self._save_unlocked()
            return json.loads(json.dumps(user))

    def add_favorite(self, user_id: int, city: str) -> List[str]:
        with self._lock:
            user = self.get_user(user_id)
            favs = user.get("favorites", [])
            normalized = city.strip()
            if normalized.lower() not in [f.lower() for f in favs]:
                favs.append(normalized)
            self.update_user(user_id, favorites=favs)
            return favs

    def remove_favorite(self, user_id: int, city: str) -> List[str]:
        with self._lock:
            user = self.get_user(user_id)
            favs = [f for f in user.get("favorites", []) if f.lower() != city.strip().lower()]
            self.update_user(user_id, favorites=favs)
            return favs

    def all_user_ids(self) -> List[int]:
        with self._lock:
            return [int(k) for k in self._data["users"].keys()]

    def users_with_daily_notify(self) -> List[Dict[str, Any]]:
        with self._lock:
            result = []
            for k, u in self._data["users"].items():
                if u.get("daily_notify", {}).get("enabled"):
                    entry = json.loads(json.dumps(u))
                    entry["user_id"] = int(k)
                    result.append(entry)
            return result

    def users_with_quake_alert(self) -> List[Dict[str, Any]]:
        with self._lock:
            result = []
            for k, u in self._data["users"].items():
                if u.get("quake_alert", {}).get("enabled"):
                    entry = json.loads(json.dumps(u))
                    entry["user_id"] = int(k)
                    result.append(entry)
            return result

    def users_with_extreme_alert(self) -> List[Dict[str, Any]]:
        with self._lock:
            result = []
            for k, u in self._data["users"].items():
                if u.get("extreme_weather_alert", {}).get("enabled"):
                    entry = json.loads(json.dumps(u))
                    entry["user_id"] = int(k)
                    result.append(entry)
            return result

    # -------------------------------------------------------------- META --
    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get("_meta", {}).get(key, default)

    def set_meta(self, key: str, value: Any) -> None:
        with self._lock:
            self._data.setdefault("_meta", {})[key] = value
            self._save_unlocked()

    def stats(self) -> Dict[str, int]:
        with self._lock:
            users = self._data["users"]
            return {
                "total_users": len(users),
                "daily_notify_active": sum(1 for u in users.values() if u.get("daily_notify", {}).get("enabled")),
                "quake_alert_active": sum(1 for u in users.values() if u.get("quake_alert", {}).get("enabled")),
                "extreme_alert_active": sum(1 for u in users.values() if u.get("extreme_weather_alert", {}).get("enabled")),
            }
