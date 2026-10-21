# ARUS: Dasbor Kelistrikan Indonesia

![ARUS](static/img/arus-logo.png)

Website dashboard untuk tugas Integrasi Aplikasi Korporasi (EAI), tema **Energi**.
Fitur: login, peta 38 provinsi, eksplorasi dan visualisasi 5 dataset kelistrikan (rumah tangga
berlistrik, produksi listrik, kapasitas pembangkit, SMA dan SMK berlistrik), filter wilayah dan
provinsi, halaman sumber data, dan unduh CSV.

Menu: **Ringkasan** (`/dasbor`), **Eksplorasi provinsi** (`/atlas#explore`), **Bandingkan**
(`/atlas#compare`), **Data dan sumber** (`/data`). Eksplorasi dan Bandingkan adalah dashboard ARUS
buatan anggota kelompok, dipasang di kerangka web ini dan mengambil data dari `/atlas/api/data`.
Tampilannya diselaraskan: `tools/samakan_atlas.py` mengubah CSS asli ARUS
(`data/arus_styles_asli.css`) jadi `static/atlas/styles.css` (dibatasi ke `.arus`, palet dan font
web utama), lalu `static/atlas/tema.css` merapikan sisanya.

## Arsitektur

```
 [JSON / CSV / XLSX di data/mentah]                       Data-level EAI
          │  Extract → Transform → Load (Pentaho, atau etl_lokal.py)
          ▼
 ┌──────────────────────────┐
 │ Database PostgreSQL      │   provinsi + 5 tabel data + users + sumber_data
 │ (Supabase / SQLite lokal)│
 └────────────┬─────────────┘
              │ SQL
 ┌────────────▼─────────────┐                               Application Interface-level EAI
 │ Flask (app.py)           │   login, /api/gabungan, /api/data/<dataset>, /api/ringkasan
 └────────────┬─────────────┘
              │ JSON lewat HTTP
 ┌────────────▼─────────────┐
 │ Browser (HTML + Chart.js)│   halaman masuk, ringkasan, data dan sumber
 └──────────────────────────┘
```

Ini **three-tier**: user interface (templates + static), business logic (Flask), data (database).

Di dalam database ada **tiga level data**: `stg_*` (staging, salinan mentah file = duplikasi),
tabel integrasi (`provinsi`, `rumah_tangga_listrik`, …, hasil transformasi), dan view presentasi
`v_provinsi_lengkap` yang dibaca API. Setiap sinkronisasi ETL dicatat di `etl_batch` dan `etl_log`
(termasuk hash file, jadi file yang tidak berubah tidak dimuat ulang). Riwayatnya tampil di halaman
Data dan sumber. Detail di `SKEMA_DATA.md`.

## Struktur folder

```
dashboard-energi/
├── app.py            # Flask: login, halaman, API
├── db.py             # koneksi database + skema tabel
├── seed.py           # buat tabel + akun demo
├── etl_lokal.py      # ETL Python dari data/mentah (cadangan/pembanding Pentaho)
├── buat_peta.py      # ubah GeoJSON jadi static/peta.json (sekali saja)
├── tools/buat_logo.py  # bikin ulang logo ARUS (static/img/)
├── tools/samakan_atlas.py  # selaraskan CSS ARUS dengan tampilan web utama
├── data/mentah/      # 5 file asli
├── data/peta/        # GeoJSON 38 provinsi + lisensinya
├── requirements.txt
├── render.yaml       # konfigurasi deploy Render
├── .env.example      # contoh pengaturan
├── SKEMA_DATA.md     # kontrak tabel untuk temen yang pegang Pentaho
├── templates/        # HTML (Jinja)
└── static/           # CSS dan JavaScript grafik
```

## Menjalankan di laptop (Windows)

Butuh Python 3.10 atau lebih baru. Buka terminal (PowerShell) di folder ini:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python seed.py
python etl_lokal.py          # tambahkan --paksa untuk muat ulang, --pantau 5 untuk sinkron tiap 5 menit
python app.py
```

Buka http://localhost:8000 lalu masuk dengan:

- username: `admin`
- kata sandi: `energi2024`

Tanpa pengaturan apa pun, aplikasi memakai SQLite (`energi.db`). `etl_lokal.py` mengisinya dari
5 file di `data/mentah/` dan mencetak log extract, transform, validasi, dan load (bisa dipakai di laporan).

Kalau sebelumnya sudah pernah menjalankan versi data contoh, tabel lama otomatis dihapus saat
`python seed.py` dijalankan.

## Pakai database Supabase (database yang sama dengan Pentaho)

1. Buat akun di https://supabase.com, lalu **New project**. Simpan password database-nya.
2. Klik **Connect** di atas dashboard project, pilih **Session pooler**, salin connection string-nya.
3. Salin `.env.example` jadi `.env`, lalu isi:
   ```
   DATABASE_URL=postgresql://postgres.xxxxx:PASSWORDMU@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
   SECRET_KEY=string-acak-panjang
   ```
4. Jalankan `python seed.py` sekali. Ini membuat semua tabel + akun demo di Supabase.
5. Isi datanya, salah satu:
   - **Pentaho** (rencana kelompok): kirim `SKEMA_DATA.md` dan detail koneksi ke temen yang pegang ETL.
   - **Cadangan**: `python etl_lokal.py` dengan `DATABASE_URL` yang sama.
6. Kalau database sudah berisi data warehouse Pentaho (schema `dw`), web otomatis membaca dari sana
   lewat view jembatan di schema `arus`. Data `dw` tidak diubah, dan `etl_lokal.py` menolak berjalan
   supaya tidak menimpa hasil Pentaho. Paksa mode lain dengan `SUMBER_DATA=lokal` atau `SUMBER_DATA=dw`.

## Deploy ke Render (gratis)

1. Upload folder ini ke repository GitHub (file `.env` dan `energi.db` sudah di-ignore).
2. Masuk ke https://render.com dengan akun GitHub, **New > Blueprint**, pilih repository-nya.
   Render membaca `render.yaml`.
3. Saat diminta, isi `DATABASE_URL` dengan connection string Supabase.
4. Tunggu build selesai. Link website muncul di halaman service.

Catatan versi gratis:

- Website tidur setelah sekitar 15 menit tanpa pengunjung dan butuh kira-kira satu menit untuk
  bangun. Buka link-nya beberapa menit sebelum presentasi.
- Project Supabase gratis di-pause setelah seminggu tidak dipakai. Datanya aman, tinggal klik
  **Restore** di dashboard Supabase. Cek H-1 presentasi.
- Jangan pakai SQLite di Render: file di server gratis Render terhapus setiap restart.

## API

Semua endpoint butuh login (cookie session).

| Endpoint | Isi |
|---|---|
| `GET /api/meta` | daftar provinsi, wilayah, sumber data, jumlah baris |
| `GET /api/gabungan?wilayah=Papua` | satu baris per provinsi, kelima dataset digabung lewat `kode_bps`, plus faktor kapasitas dan selisih kota-desa |
| `GET /api/ringkasan?kode=96` | angka nasional, atau satu provinsi beserta peringkatnya |
| `GET /api/data/<dataset>?wilayah=&kode=&nasional=1` | isi satu tabel dalam JSON |
| `GET /api/data/<dataset>.csv` | isi satu tabel dalam CSV |

`<dataset>`: `rumah_tangga_listrik`, `produksi_listrik`, `kapasitas_pembangkit`, `sma_listrik`,
`smk_listrik`.

## Kredit

- Peta: Deny Herianto, *Indonesia GeoJSON & TopoJSON Maps (38 Provinces)*, CC BY 4.0.
  Disederhanakan dan diproyeksikan menjadi jalur SVG oleh `buat_peta.py`.
- Lima file data dan sebagian catatan metodologi berasal dari prototipe ARUS buatan anggota kelompok.

## Keamanan

- Kata sandi disimpan sebagai hash (Werkzeug), bukan teks asli.
- Query memakai parameter, dan nama tabel API dibatasi ke daftar yang diizinkan.
- Halaman dan API ditolak kalau belum login.
- Matikan halaman "Buat akun" dengan `ALLOW_REGISTER=0` kalau tidak dibutuhkan.
