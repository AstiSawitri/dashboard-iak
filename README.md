# ARUS: Dasbor Kelistrikan Indonesia

![ARUS](static/img/arus-logo.png)

Website dashboard untuk tugas mata kuliah **Integrasi Aplikasi Korporasi**, tema **Energi**.
ARUS menggabungkan lima dataset kelistrikan per provinsi supaya terlihat provinsi mana yang
listriknya sudah merata dan mana yang belum.

**Website:** https://dashboard-iak-sand.vercel.app
(masuk dengan username `admin`, kata sandi `energi2024`)

## Fitur

- Login dan buat akun (kata sandi disimpan sebagai hash).
- **Ringkasan** (`/dasbor`): angka nasional, peta 38 provinsi, peringkat, dan grafik per indikator.
- **Eksplorasi provinsi** (`/atlas#explore`): pilih indikator dan provinsi, lihat profil lengkapnya.
- **Bandingkan** (`/atlas#compare`): bandingkan dua provinsi berdampingan.
- **Data dan sumber** (`/data`): asal tiap dataset, alur ETL, riwayat sinkronisasi, isi tabel, dan
  unduh CSV.
- Filter wilayah (Sumatera, Jawa, Kalimantan, dan seterusnya) dan provinsi.

## Dataset

Lima dataset dengan tiga format file asal, digabung per provinsi lewat kode wilayah BPS.

| Dataset | Format asal | Sumber | Tahun |
|---|---|---|---|
| Persentase rumah tangga dengan sumber penerangan utama listrik (kota, desa, total) | JSON | Badan Pusat Statistik (BPS), Susenas Maret | 2024 |
| Tenaga listrik yang dibangkitkan (GWh) | CSV | Badan Pusat Statistik (BPS) | 2024 |
| Kapasitas terpasang pembangkit listrik (MW) | XLSX | Badan Pusat Statistik (BPS) | 2024 |
| Proporsi SMA yang memiliki akses listrik (negeri, swasta, total) | XLSX | Satu Data, Pusdatin Kementerian Pendidikan Dasar dan Menengah | 2023 |
| Proporsi SMK yang memiliki akses listrik (negeri, swasta, total) | XLSX | Satu Data, Pusdatin Kementerian Pendidikan Dasar dan Menengah | 2023 |

File aslinya ada di `data/mentah/`.

## Arsitektur

```
 [JSON / CSV / XLSX]                                    Data-level integration
          │  Extract → Transform → Load (Pentaho Data Integration)
          ▼
 ┌────────────────────────────────┐
 │ PostgreSQL di Supabase         │   schema stg  : staging, salinan mentah file (duplikasi)
 │                                │   schema dw   : data warehouse, tabel dimensi + fakta
 │                                │   schema arus : view jembatan + view v_provinsi_lengkap
 └───────────────┬────────────────┘
                 │ SQL
 ┌───────────────▼────────────────┐                     Application interface-level integration
 │ Flask (app.py)                 │   login, API JSON dan CSV
 └───────────────┬────────────────┘
                 │ JSON lewat HTTP
 ┌───────────────▼────────────────┐
 │ Browser (HTML, CSS, Chart.js)  │   ringkasan, eksplorasi, bandingkan, data dan sumber
 └────────────────────────────────┘
```

Aplikasi ini **three-tier**: tampilan (`templates/`, `static/`), logika (Flask), dan data
(PostgreSQL).

### Alur ETL

1. **Duplikasi (staging).** Pentaho menyalin isi tiap file apa adanya ke schema `stg`.
2. **Transformasi.** Nama provinsi diseragamkan, angka dibersihkan, kode BPS dipasang, lalu data
   dimuat ke schema `dw` sebagai tabel dimensi (`dim_provinsi`, `dim_tahun`, `dim_dataset`,
   `dim_klasifikasi_wilayah`, `dim_jenjang_sekolah`, `dim_status_sekolah`) dan tabel fakta
   (`fact_listrik_dibangkitkan`, `fact_kapasitas_pembangkit`, `fact_akses_listrik_rt`,
   `fact_akses_listrik_sekolah`).
3. **Sinkronisasi.** Setiap baris fakta mencatat waktu muat (`etl_loaded_at`). Web membaca dari view,
   jadi begitu Pentaho memuat ulang data, dasbor langsung ikut berubah tanpa perlu diubah kodenya.

Web tidak pernah mengubah schema `stg` dan `dw`. Saat aplikasi menyala, `db.py` membuat view jembatan
di schema `arus` yang mengubah bentuk dimensi dan fakta menjadi satu baris per provinsi
(`v_provinsi_lengkap`). Jumlah baris tiap lapisan dan waktu muat terakhir tampil di halaman
**Data dan sumber**.

Sebagai pembanding, `etl_lokal.py` menjalankan alur yang sama dengan Python ke SQLite (staging,
integrasi, presentasi, dengan log dan hash file). Skrip ini hanya untuk percobaan di laptop dan
otomatis menolak berjalan kalau database berisi data warehouse Pentaho.

## Struktur folder

```
dashboard-energi/
├── app.py              # Flask: login, halaman, API
├── db.py               # koneksi database, view jembatan ke data warehouse
├── seed.py             # siapkan tabel users + akun admin
├── etl_lokal.py        # ETL Python pembanding (SQLite)
├── buat_peta.py        # ubah GeoJSON jadi static/peta.json
├── tools/
│   ├── buat_logo.py      # bikin ulang logo ARUS
│   └── samakan_atlas.py  # selaraskan CSS halaman Eksplorasi/Bandingkan dengan web utama
├── data/mentah/        # 5 file data asli
├── data/peta/          # GeoJSON 38 provinsi + lisensinya
├── templates/          # HTML (Jinja)
├── static/             # CSS, JavaScript, gambar
├── SKEMA_DATA.md       # struktur tabel dan kolom
├── requirements.txt
├── vercel.json         # konfigurasi deploy Vercel
└── .env.example        # contoh pengaturan
```

## Menjalankan di laptop (Windows)

Butuh Python 3.10 atau lebih baru. Buka PowerShell di folder ini:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Salin `.env.example` menjadi `.env`, lalu isi `DATABASE_URL` dengan connection string Supabase
(menu **Connect → Session pooler**) dan `SECRET_KEY` dengan teks acak. Setelah itu:

```powershell
python seed.py
python app.py
```

Buka http://localhost:8000 dan masuk dengan `admin` / `energi2024`.

Kalau `DATABASE_URL` dikosongkan, aplikasi memakai SQLite (`energi.db`). Isi datanya dengan
`python etl_lokal.py`.

## Deploy ke Vercel

1. Push folder ini ke GitHub. File `.env` dan `energi.db` tidak ikut karena sudah di-ignore.
2. Di https://vercel.com, masuk dengan akun GitHub, pilih **Add New → Project**, lalu import
   repository-nya.
3. Di **Settings → Environment Variables**, isi `DATABASE_URL` (connection string Supabase) dan
   `SECRET_KEY`.
4. Deploy. Setiap `git push` ke branch `main` akan men-deploy ulang otomatis.

Server diatur di region Singapura (`sin1`) supaya dekat dengan database Supabase. Halaman `/status`
menampilkan apakah koneksi ke database berhasil, tanpa membuka password.

Project Supabase gratis di-pause setelah seminggu tidak dipakai. Datanya tetap aman, tinggal klik
**Restore** di dashboard Supabase.

## API

Semua endpoint butuh login.

| Endpoint | Isi |
|---|---|
| `GET /api/meta` | daftar provinsi, wilayah, sumber data, jumlah baris |
| `GET /api/gabungan?wilayah=Papua` | satu baris per provinsi, kelima dataset digabung lewat kode BPS |
| `GET /api/ringkasan?kode=96` | angka nasional, atau satu provinsi beserta peringkatnya |
| `GET /api/data/<dataset>?wilayah=&kode=&nasional=1` | isi satu dataset dalam JSON |
| `GET /api/data/<dataset>.csv` | isi satu dataset dalam CSV |
| `GET /api/etl` | jumlah baris tiap lapisan ETL dan riwayat sinkronisasi |
| `GET /atlas/api/data` | data untuk halaman Eksplorasi dan Bandingkan |

`<dataset>`: `rumah_tangga_listrik`, `produksi_listrik`, `kapasitas_pembangkit`, `sma_listrik`,
`smk_listrik`.

## Keamanan

- Kata sandi disimpan sebagai hash (Werkzeug), bukan teks asli.
- Query memakai parameter, dan nama dataset di API dibatasi ke daftar yang diizinkan.
- Halaman dan API ditolak kalau belum login.
- Password database hanya disimpan di `.env` dan Environment Variables Vercel, tidak di GitHub.

## Kredit

- Peta: Deny Herianto, *Indonesia GeoJSON & TopoJSON Maps (38 Provinces)*, CC BY 4.0.
- Data: Badan Pusat Statistik dan Satu Data Kementerian Pendidikan Dasar dan Menengah.
