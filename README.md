# 🌤️ WeatherBot — Bot Telegram Cuaca, Kualitas Udara & Gempa (Indonesia)

Bot Telegram full-button dengan animasi loading, notifikasi push otomatis
(ramalan harian, alert gempa, alert cuaca ekstrem), grafik cuaca, inline mode,
dan penyimpanan data TANPA database server (cukup file JSON).

Semua logika inti (fetch data, format pesan, keyboard, scheduler) sudah
diuji lewat test otomatis yang mensimulasikan Bot API Telegram — lihat
bagian [Testing](#-testing) di bawah.

---

## ✨ Fitur

- 🌤️ Cek cuaca kota manapun (ketik nama, tombol, atau kirim lokasi 📍)
- ⭐ Kota favorit (simpan banyak, buka cepat lewat tombol)
- 📊 Grafik suhu & peluang hujan per jam (gambar, dark-mode)
- 📅 Ramalan 3 hari, 🌍 detail gempa (terbaru, M5+, dirasakan warga)
- 🌫️ Kualitas udara + saran kesehatan
- 🚨 Status ringkas otomatis ("WASPADA") kalau ada kondisi ekstrem
- 🔔 Notifikasi push: ramalan harian terjadwal, alert gempa (ambang
  magnitudo bisa diatur), alert cuaca ekstrem — semua jalan di background
- ⚙️ Ganti satuan °C/°F dan bahasa ID/EN
- 📄 Ekspor laporan cuaca jadi file teks
- 🔍 Inline mode: ketik `@namabot jakarta` di chat manapun
- 🎬 Animasi: spinner + progress bar saat loading, progressive reveal,
  emoji reaction otomatis pada kondisi ekstrem, chat action ("mengetik...")

## 🗂️ Struktur Project

```
weatherbot/
├── bot.py                 # entry point — jalankan ini
├── config.py               # baca .env / environment variable
├── storage.py               # penyimpanan JSON (bukan database) + tested
├── weather_api.py            # fetch wttr.in, Open-Meteo, BMKG + tested
├── weather_render.py          # data mentah -> teks pesan HTML + tested
├── charts.py                   # grafik PNG dark-mode + tested (real matplotlib)
├── texts.py                     # semua string ID/EN + tested (key-parity)
├── keyboards.py                  # semua inline keyboard + tested
├── animations.py                  # spinner/progress bar/reaction + tested
├── scheduler.py                    # 3 job notifikasi push + tested
├── states.py                        # FSM states
└── handlers/                         # semua handler per topik
    ├── start.py, weather.py, favorites.py,
    ├── settings.py, notifications.py, export.py, inline_mode.py
```

Prinsip desain: **pemisahan tegas antara logika murni dan I/O Telegram**.
`weather_render.py`, `weather_api.py`, `storage.py`, `charts.py`, `texts.py`
tidak menyentuh aiogram sama sekali — bisa dites tanpa mock Telegram apa
pun. Handler di folder `handlers/` cuma "merangkai" potongan-potongan itu.

## 🚀 Cara Menjalankan

```bash
# 1. Buat virtual environment (opsional tapi disarankan)
python3 -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate

# 2. Install dependency
pip install -r requirements.txt

# 3. Isi token bot
nano config.py               # cari BOT_TOKEN, ganti dengan token dari @BotFather

# 4. Jalankan
python3 bot.py
```

Konfigurasi (token, direktori data, interval scheduler, dll) semuanya ada
langsung di `config.py` sebagai variabel biasa — tidak pakai `.env` atau
environment variable, tinggal edit file-nya langsung.

Bot jalan pakai **polling** (sesuai kesepakatan kita) — tidak butuh domain
atau SSL, langsung jalan begitu dijalankan.

## 🌐 Sumber Data

Semua gratis, tanpa perlu daftar API key:

| Sumber | Fungsi |
|---|---|
| **wttr.in** | Cuaca, suhu, ramalan |
| **Open-Meteo** (air-quality-api) | Kualitas udara (AQI) |
| **BMKG** (data.bmkg.go.id) | Gempa, peringatan dini |
| **Nominatim** (OpenStreetMap) | Reverse-geocode nama tempat dari koordinat — cuma dipanggil sebagai *fallback* kalau wttr.in tidak menyertakan nama area untuk lokasi tersebut |

⚠️ **Sebelum deploy serius**, buka `weather_api.py`, cari `NOMINATIM_USER_AGENT`,
dan ganti `contact@example.com` dengan kontak asli kamu (email/URL project).
Ini wajib menurut [kebijakan penggunaan Nominatim](https://operations.osmfoundation.org/policies/nominatim/)
— server publik mereka bisa mem-blokir User-Agent yang tidak jelas identitasnya.

## 🖥️ Deploy Permanen di VPS (systemd)

Supaya bot tetap jalan walau kamu logout / VPS restart:

```bash
sudo nano /etc/systemd/system/weatherbot.service
```

```ini
[Unit]
Description=WeatherBot Telegram
After=network.target

[Service]
Type=simple
User=namauser
WorkingDirectory=/path/ke/weatherbot
ExecStart=/path/ke/weatherbot/venv/bin/python3 bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now weatherbot
sudo systemctl status weatherbot     # cek status
journalctl -u weatherbot -f          # lihat log real-time
```

## 💾 Soal Penyimpanan Data (Tanpa Database)

Semua data user (favorit, jadwal notifikasi, pengaturan) disimpan di
`data/users.json` — satu file JSON, ditulis atomic (aman dari corrupt saat
crash), dengan backup otomatis (`users.json.bak`). Cocok untuk skala
personal sampai menengah. Kalau nanti botnya dipakai ribuan orang aktif
dan butuh query lebih kompleks, struktur `DEFAULT_USER` di `storage.py`
sudah dirancang supaya gampang dipetakan ke tabel SQL tanpa mengubah kode
pemanggilnya (`get_user`, `update_user`, dst tinggal diganti implementasinya).

## 🔔 Cara Kerja Notifikasi Push

`scheduler.py` menjalankan 3 job pakai APScheduler:

| Job | Interval | Logika anti-spam |
|---|---|---|
| Ramalan harian | tiap menit | dedup per hari (`last_sent_date`) |
| Alert gempa | tiap 60 detik | dedup per event gempa (`last_alerted_quake_id`), baseline di-set dulu saat bot start (tidak broadcast gempa lama) |
| Alert cuaca ekstrem | tiap 30 menit | cooldown 3 jam per user sebelum boleh kirim ulang |

Semua fetch API dikelompokkan per **kota unik**, bukan per user — jadi
kalau 100 user subscribe ramalan harian kota Jakarta, cuma 1x fetch API,
bukan 100x.

## 🎬 Soal Animasi

Telegram bot (mode klasik, bukan Mini App/WebApp) tidak bisa render CSS
animation beneran. Yang dipakai di sini supaya terasa hidup:
- Spinner braille + progress bar yang diedit berulang (`animations.py`)
- Chat action native ("sedang mengetik...")
- Progressive reveal (info nongol bertahap, bukan sekaligus)
- Emoji reaction otomatis dari bot ke pesan user saat ada kondisi ekstrem
- Grafik PNG dark-mode yang matching tema Telegram

Kalau ke depannya kamu mau animasi yang BENERAN gerak (transisi halus,
chart interaktif, swipe), itu perlu upgrade ke **Telegram Mini App
(WebApp)** — arsitektur berbeda (perlu web server + HTTPS). Kode di
`weather_render.py`, `weather_api.py`, `storage.py` bisa dipakai ulang
langsung karena tidak bergantung pada aiogram.

## 🧪 Testing

Semua modul non-Telegram (storage, weather_api, texts, charts,
weather_render) sudah lolos unit test dengan HTTP di-mock / data asli.
Seluruh handler + scheduler sudah lolos **test integrasi end-to-end**
yang mensimulasikan ~20 langkah perjalanan user asli (start → cek cuaca →
favorit → notifikasi → settings → export → inline mode → error handling)
memakai stub minimal aiogram, tanpa perlu bot token/koneksi Telegram
sungguhan. Ini menangkap beberapa bug nyata sebelum kode ini sampai ke
kamu (misal konflik nama parameter di sistem terjemahan).

Kalau mau menjalankan ulang test tersebut, beri tahu saya — test harness-nya
tidak disertakan di paket ini (khusus dipakai selama development) supaya
project yang kamu terima tetap ringkas dan production-ready.

> **Catatan transparansi:** saat menambahkan reverse-geocoding, test
> end-to-end sempat menangkap bug tersembunyi — validasi nama kota
> (`validate_city`) menolak format koordinat `"lat,lon"`, jadi fitur
> "kirim lokasi 📍" sebenarnya SELALU gagal sejak awal. Sudah diperbaiki
> dan sekarang teruji jalan normal (termasuk 2 jalur: nama area langsung
> dari wttr.in, dan fallback ke Nominatim kalau kosong).

## ➕ Menambah Fitur Baru

Berkat pemisahan modul, pola untuk nambah fitur baru:
1. Fitur butuh data baru dari API? → tambah method di `weather_api.py`
2. Fitur butuh format pesan baru? → tambah fungsi di `weather_render.py`
3. Fitur butuh tombol baru? → tambah builder di `keyboards.py`
4. Fitur butuh teks baru? → tambah key di `texts.py` (ID **dan** EN)
5. Rangkai semuanya di file handler baru / yang sudah ada di `handlers/`
6. Daftarkan router-nya di `handlers/__init__.py` kalau bikin file baru

## ⚠️ Batasan yang Perlu Diketahui

- Filter wilayah pada alert gempa (`region_keyword`) sudah ada di skema
  data tapi belum ada UI-nya di menu (baru bisa lewat magnitudo). Gampang
  ditambah kalau dibutuhkan — tinggal 1 langkah FSM tambahan mirip alur
  ketik kota manual.
- Broadcast (kirim pesan ke semua user, misal buat pengumuman admin)
  belum ada. `ADMIN_IDS` di config sudah disiapkan sebagai pondasi kalau
  mau ditambah nanti.
- Nominatim (server publik OSM) punya rate limit ketat (kira-kira 1
  request/detik). Karena cuma dipanggil saat wttr.in tidak kasih nama
  area DAN hasilnya di-cache lama (data lokasi jarang berubah), ini aman
  untuk pemakaian normal. Kalau botnya nanti dipakai ribuan user yang
  sering kirim lokasi baru, pertimbangkan pindah ke provider geocoding
  berbayar (Google/Mapbox) atau self-host instance Nominatim sendiri.
