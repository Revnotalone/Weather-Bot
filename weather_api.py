# -*- coding: utf-8 -*-
"""
Lapisan pengambilan data (cuaca, kualitas udara, gempa, peringatan dini).

Ini adalah versi bot dari logika yang sudah diuji habis-habisan di
`dashboard.py` (CLI dashboard) — dipindah ke sini apa adanya (retry, cache
disk, error handling eksplisit, tidak ada `except: pass`), lalu dipanggil
dari handler async lewat `asyncio.to_thread()` supaya tidak memblokir
event loop bot.
"""
from __future__ import annotations

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    from requests.packages.urllib3.util.retry import Retry  # type: ignore

logger = logging.getLogger("weatherbot.weather_api")

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
USER_AGENT = "weatherbot-telegram/1.0"

WTTR_URL_TMPL = "https://wttr.in/{city}?format=j1"
OPEN_METEO_AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
BMKG_WARNING_URL = "https://data.bmkg.go.id/DataMKG/MEWS/warning/WarningCuaca.xml"
BMKG_AUTOGEMPA_URL = "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json"
BMKG_GEMPATERKINI_URL = "https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json"
BMKG_DIRASAKAN_URL = "https://data.bmkg.go.id/DataMKG/TEWS/gempadirasakan.json"

AQI_CATEGORIES = [
    (0, 50, "Baik", "🟢", "Kualitas udara memuaskan, risiko minimal."),
    (51, 100, "Sedang", "🟡", "Cukup dapat diterima; kelompok sensitif waspada."),
    (101, 150, "Tidak Sehat (Sensitif)", "🟠",
     "Anak-anak, lansia, dan penderita gangguan pernapasan sebaiknya kurangi aktivitas luar ruangan."),
    (151, 200, "Tidak Sehat", "🔴", "Semua orang mulai terdampak; kurangi aktivitas berat di luar ruangan."),
    (201, 300, "Sangat Tidak Sehat", "🟣", "Peringatan kesehatan darurat; hindari aktivitas luar ruangan."),
    (301, 10_000, "Berbahaya", "🟤", "Kondisi darurat kesehatan; seluruh populasi berisiko tinggi."),
]


class DashboardError(Exception):
    pass


class DataSourceError(DashboardError):
    def __init__(self, source: str, message: str):
        self.source = source
        super().__init__(f"[{source}] {message}")


class InvalidCityError(DashboardError):
    pass


CITY_NAME_RE = re.compile(r"^[A-Za-z\u00C0-\u024F\s\.'\-,]{2,80}$")
COORDS_RE = re.compile(r"^-?\d{1,3}(\.\d+)?,\s*-?\d{1,3}(\.\d+)?$")

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
# Nominatim WAJIB diberi User-Agent yang jelas identitasnya (bukan default
# requests) sesuai kebijakan penggunaannya: https://operations.osmfoundation.org/policies/nominatim/
# Ganti "contact@example.com" dengan kontak asli kamu sebelum dipakai serius.
NOMINATIM_USER_AGENT = "weatherbot-telegram/1.0 (cynsar5e@gmail.com)"


def validate_city(city: str) -> str:
    city = city.strip()
    if not city:
        raise InvalidCityError("Nama kota tidak boleh kosong.")
    if len(city) > 80:
        raise InvalidCityError("Nama kota terlalu panjang.")

    if COORDS_RE.match(city):
        # Format "lat,lon" (dipakai saat user kirim lokasi) — validasi
        # rentang koordinat, bukan aturan nama kota.
        try:
            lat_str, lon_str = [p.strip() for p in city.split(",")]
            lat, lon = float(lat_str), float(lon_str)
        except ValueError:
            raise InvalidCityError("Format koordinat tidak valid.")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise InvalidCityError("Koordinat di luar rentang valid (lat -90..90, lon -180..180).")
        return city

    if not CITY_NAME_RE.match(city):
        raise InvalidCityError(
            "Nama kota mengandung karakter tidak valid (hanya huruf, spasi, titik, koma, strip)."
        )
    return city


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES, backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",), raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


class DiskCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe_key = re.sub(r"[^a-zA-Z0-9_\-]", "_", key)
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str, ttl: int) -> Tuple[Optional[Any], bool]:
        path = self._path(key)
        if not path.exists():
            return None, False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            age = time.time() - payload.get("_cached_at", 0)
            return payload.get("data"), age > ttl
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cache rusak key=%s: %s", key, e)
            return None, False

    def set(self, key: str, data: Any) -> None:
        path = self._path(key)
        try:
            path.write_text(
                json.dumps({"_cached_at": time.time(), "data": data}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("Gagal tulis cache key=%s: %s", key, e)


class WeatherClient:
    """Klien terpusat untuk semua sumber data. Semua method SINKRON —
    panggil lewat asyncio.to_thread() dari kode async."""

    def __init__(self, cache_dir: Path, cache_ttl: int = 300, use_cache: bool = True):
        self.session = build_session()
        self.cache = DiskCache(cache_dir)
        self.cache_ttl = cache_ttl
        self.use_cache = use_cache

    def _get_json(self, url: str, cache_key: str, source: str,
                   params: Optional[dict] = None) -> Tuple[Any, bool]:
        try:
            resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if self.use_cache:
                self.cache.set(cache_key, data)
            return data, False
        except requests.exceptions.RequestException as e:
            logger.warning("%s: live fetch gagal (%s)", source, e)
        except ValueError as e:
            logger.warning("%s: respons bukan JSON valid (%s)", source, e)

        if self.use_cache:
            cached, is_stale = self.cache.get(cache_key, self.cache_ttl)
            if cached is not None:
                logger.info("%s: pakai cache (%s)", source, "basi" if is_stale else "segar")
                return cached, True

        raise DataSourceError(source, "tidak ada data live maupun cache")

    def get_weather(self, city: str) -> Dict[str, Any]:
        city = validate_city(city)
        url = WTTR_URL_TMPL.format(city=requests.utils.quote(city))
        data, stale = self._get_json(url, f"weather_{city.lower()}", "Cuaca (wttr.in)")
        if "current_condition" not in data:
            raise DataSourceError("Cuaca (wttr.in)", f"kota '{city}' tidak dikenali")
        data["_stale"] = stale
        return data

    def resolve_location_name(self, lat: float, lon: float) -> Optional[str]:
        """Reverse-geocoding lewat Nominatim (OpenStreetMap) — cuma dipanggil
        sebagai FALLBACK kalau wttr.in tidak menyertakan nama area yang jelas
        untuk koordinat yang diberikan (lihat `extract_area_name`). Hasilnya
        di-cache cukup lama karena nama lokasi jarang berubah, supaya tidak
        membebani server publik Nominatim (kebijakan mereka: pakai seperlunya,
        User-Agent wajib jelas, jangan di-hammer)."""
        cache_key = f"geocode_{lat:.3f}_{lon:.3f}"
        long_ttl = self.cache_ttl * 12  # nama lokasi jarang berubah, cache lebih awet
        cached, is_stale = (None, True)
        if self.use_cache:
            cached, is_stale = self.cache.get(cache_key, long_ttl)
            if cached is not None and not is_stale:
                return cached

        try:
            resp = self.session.get(
                NOMINATIM_REVERSE_URL,
                params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "accept-language": "id"},
                headers={"User-Agent": NOMINATIM_USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            address = data.get("address", {})
            name = (address.get("city") or address.get("town") or address.get("municipality")
                    or address.get("village") or address.get("county") or address.get("state"))
            if name:
                if self.use_cache:
                    self.cache.set(cache_key, name)
                return name
        except requests.exceptions.RequestException as e:
            logger.warning("Reverse geocoding (Nominatim) gagal: %s", e)
        except ValueError as e:
            logger.warning("Reverse geocoding: respons bukan JSON valid (%s)", e)

        return cached  # None kalau memang tidak ada cache sama sekali

    def get_air_quality(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        params = {
            "latitude": lat, "longitude": lon,
            "current": "european_aqi,us_aqi,pm2_5,pm10,carbon_monoxide,"
                       "nitrogen_dioxide,sulphur_dioxide,ozone",
            "timezone": "auto",
        }
        try:
            data, _ = self._get_json(
                OPEN_METEO_AQI_URL, f"aqi_{lat:.2f}_{lon:.2f}", "Kualitas Udara", params
            )
            return data.get("current", {})
        except DataSourceError as e:
            logger.warning(str(e))
            return None

    def get_bmkg_warnings(self) -> List[Dict[str, str]]:
        source = "Peringatan Dini (BMKG)"
        cache_key = "bmkg_warnings"
        try:
            resp = self.session.get(BMKG_WARNING_URL, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            content = resp.content
            if self.use_cache:
                self.cache.set(cache_key, content.decode("utf-8", errors="replace"))
        except requests.exceptions.RequestException as e:
            logger.warning("%s: live fetch gagal (%s)", source, e)
            if not self.use_cache:
                return []
            cached, _ = self.cache.get(cache_key, self.cache_ttl)
            if cached is None:
                return []
            content = cached.encode("utf-8")

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.error("%s: XML tidak valid (%s)", source, e)
            return []

        warnings: List[Dict[str, str]] = []
        for w in (root.findall(".//warning") or root.findall(".//Warning")):
            def first_text(tags: List[str]) -> str:
                for t in tags:
                    val = w.findtext(t)
                    if val:
                        return val.strip()
                return ""
            area = first_text(["area", "Area", "region"])
            event = first_text(["type", "Type", "event", "phenomena"])
            valid_from = first_text(["valid_from", "validfrom", "issued"])
            valid_to = first_text(["valid_to", "validto", "expires"])
            if not (area or event):
                continue
            warnings.append({
                "area": area or "Tidak diketahui", "event": event or "Tidak diketahui",
                "time": f"{valid_from} - {valid_to}".strip(" -"),
            })
        return warnings

    def get_earthquake_latest(self) -> Optional[Dict[str, Any]]:
        try:
            data, _ = self._get_json(BMKG_AUTOGEMPA_URL, "gempa_terbaru", "Gempa Terbaru")
            return data.get("Infogempa", {}).get("gempa", {})
        except DataSourceError as e:
            logger.warning(str(e))
            return None

    def get_earthquake_recent_list(self, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            data, _ = self._get_json(BMKG_GEMPATERKINI_URL, "gempa_terkini_list", "Gempa M5+ Terkini")
            gempa_list = data.get("Infogempa", {}).get("gempa", [])
            if isinstance(gempa_list, dict):
                gempa_list = [gempa_list]
            return gempa_list[:limit]
        except DataSourceError as e:
            logger.warning(str(e))
            return []

    def get_earthquake_felt(self, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            data, _ = self._get_json(BMKG_DIRASAKAN_URL, "gempa_dirasakan", "Gempa Dirasakan")
            gempa_list = data.get("Infogempa", {}).get("gempa", [])
            if isinstance(gempa_list, dict):
                gempa_list = [gempa_list]
            return gempa_list[:limit]
        except DataSourceError as e:
            logger.warning(str(e))
            return []


# ------------------------------------------------------------------ utils --
def extract_value(val: Any) -> str:
    if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
        return str(val[0].get("value", val))
    return str(val) if val is not None else "N/A"


def extract_area_name(weather_data: Dict[str, Any]) -> Optional[str]:
    """Ambil nama area dari respons wttr.in (field `nearest_area`), dipakai
    sebagai sumber UTAMA nama lokasi saat user kirim koordinat — supaya
    Nominatim cuma jadi fallback, bukan dipanggil setiap saat."""
    area = weather_data.get("nearest_area", [])
    if not area:
        return None
    name = extract_value(area[0].get("areaName", ""))
    region = extract_value(area[0].get("region", ""))
    if not name or name == "N/A":
        return None
    if region and region != "N/A" and region.lower() != name.lower():
        return f"{name}, {region}"
    return name


def c_to_f(c: float) -> float:
    return c * 9 / 5 + 32


def format_temp(value: Any, unit: str) -> str:
    try:
        c = float(value)
    except (ValueError, TypeError):
        return f"{value}"
    if unit == "f":
        return f"{c_to_f(c):.1f}°F"
    return f"{c:.0f}°C"


def aqi_category(us_aqi: Any) -> Tuple[str, str, str]:
    try:
        val = float(us_aqi)
    except (ValueError, TypeError):
        return "N/A", "⚪", "Data tidak tersedia."
    for low, high, label, icon, advice in AQI_CATEGORIES:
        if low <= val <= high:
            return label, icon, advice
    return "N/A", "⚪", "Data tidak tersedia."


def weather_icon(desc: str) -> str:
    """Pilih emoji ikon cuaca berdasar deskripsi teks dari wttr.in."""
    d = desc.lower()
    if "thunder" in d or "petir" in d:
        return "⛈️"
    if "snow" in d or "salju" in d:
        return "🌨️"
    if "rain" in d or "drizzle" in d or "hujan" in d:
        return "🌧️"
    if "overcast" in d:
        return "☁️"
    if "cloud" in d or "berawan" in d:
        return "⛅"
    if "fog" in d or "mist" in d or "kabut" in d:
        return "🌫️"
    if "clear" in d or "sunny" in d or "cerah" in d:
        return "☀️"
    return "🌤️"
