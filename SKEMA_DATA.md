# Skema data untuk hasil ETL (Pentaho)

Dokumen ini buat temen yang pegang ETL. Website membaca **6 tabel data** di bawah (1 tabel provinsi +
5 dataset). Selama hasil Pentaho masuk ke tabel dan kolom dengan nama yang sama persis, dashboard
langsung memakainya tanpa perlu ubah kode.

Sebagai pembanding, `etl_lokal.py` mengerjakan alur yang sama dengan Python. Kalau ETL Pentaho benar,
isi tabelnya sama persis dengan hasil skrip itu. Jalankan `python etl_lokal.py` lalu bandingkan.

## File mentah (folder `data/mentah/`)

| File | Format | Isi | Tahun |
|---|---|---|---|
| `rumah_tangga_listrik_2024.json` | JSON (API tabel dinamis BPS) | % rumah tangga dengan penerangan utama dari listrik, kota/desa | 2024 |
| `produksi_listrik_2024.csv` | CSV | Tenaga listrik yang dibangkitkan (GWh) | 2024 |
| `kapasitas_pembangkit_2024.xlsx` | XLSX | Kapasitas terpasang pembangkit (MW) | 2024 |
| `sma_akses_listrik.xlsx` | XLSX, sheet `data` | % SMA yang punya akses listrik, negeri/swasta/total | **2023** (lihat judul di sel A1) |
| `smk_akses_listrik.xlsx` | XLSX, sheet `data` | % SMK yang punya akses listrik, negeri/swasta/total | **2023** |

## Kunci penghubung: `kode_bps`

Semua tabel memakai **kode provinsi BPS 2 digit** (11 = Aceh, 31 = DKI Jakarta, 97 = Papua Pegunungan).
Baris nasional (INDONESIA) disimpan dengan **`kode_bps = 99`**.

- JSON memberi kode 4 digit (`1100`, `9999`): bagi 100.
- File SMA/SMK punya kolom **Kode BPS** dan **Kode Kemdagri**. Pakai **Kode BPS**. Untuk provinsi Papua
  keduanya berbeda (contoh: Papua Tengah, Kode BPS 96, Kode Kemdagri 94).
- CSV dan XLSX kapasitas tidak punya kode, hanya nama huruf besar (`KEP. RIAU`). Cocokkan lewat nama ke
  tabel `provinsi` setelah dinormalisasi: huruf besar, spasi dirapikan, `KEPULAUAN` disamakan dengan `KEP.`.

## Tabel tujuan

### `provinsi` (dari JSON, bagian `vervar`)
| Kolom | Tipe | Contoh | Aturan |
|---|---|---|---|
| kode_bps | INTEGER, PK | 96 | `val / 100` |
| nama | VARCHAR(60) | Papua Tengah | `label`, huruf kapital di awal kata; `DKI Jakarta`, `DI Yogyakarta`, `KEP.` → `Kepulauan` |
| wilayah | VARCHAR(40) | Papua | 11–21 Sumatera, 31–36 Jawa, 51–53 Bali dan Nusa Tenggara, 61–65 Kalimantan, 71–76 Sulawesi, 81–82 Maluku, 91–97 Papua, 99 Nasional |

### `rumah_tangga_listrik` (JSON)
| Kolom | Tipe | Contoh |
|---|---|---|
| kode_bps | INTEGER | 96 |
| tahun | INTEGER | 2024 |
| perkotaan_persen | DOUBLE PRECISION, boleh NULL | 100 |
| perdesaan_persen | DOUBLE PRECISION, boleh NULL | 43.46 |
| total_persen | DOUBLE PRECISION, boleh NULL | 56.08 |

Isi angka ada di objek `datacontent`, kuncinya gabungan kode:
`kode wilayah (4 digit) + kode var (853) + kode turvar + kode tahun (124) + kode turtahun (0)`.
Kode turvar: `189` Perkotaan, `190` Perdesaan, `191` Perkotaan+Perdesaan.
Contoh: `96008531901240` = Papua Tengah, perdesaan, 2024 → 43.46.

DKI Jakarta tidak punya angka perdesaan. **Simpan NULL, jangan 0.**

### `produksi_listrik` (CSV)
| Kolom | Tipe | Contoh |
|---|---|---|
| kode_bps | INTEGER | 33 |
| tahun | INTEGER | 2024 |
| produksi_gwh | DOUBLE PRECISION | 71068.16 |

Tiga baris pertama CSV adalah judul (`38 Provinsi`, nama tabel, `2024`). Lewati, tapi ambil tahun dari baris ketiga.

### `kapasitas_pembangkit` (XLSX)
| Kolom | Tipe | Contoh |
|---|---|---|
| kode_bps | INTEGER | 33 |
| tahun | INTEGER | 2024 |
| kapasitas_mw | DOUBLE PRECISION | 12814.08 |

Bentuknya sama dengan CSV. Angkanya tersimpan sebagai **teks** di Excel, jadi ubah ke angka.

### `sma_listrik` dan `smk_listrik` (XLSX, sheet `data`)
| Kolom | Tipe | Contoh |
|---|---|---|
| kode_bps | INTEGER | 97 |
| tahun | INTEGER | 2023 |
| negeri_persen | DOUBLE PRECISION | 88.64 |
| swasta_persen | DOUBLE PRECISION | 94.44 |
| total_persen | DOUBLE PRECISION | 90.32 |

- Header ada di baris 2 dan 3 (sel bergabung). Data mulai baris 4.
- Ambil tahun dari judul di A1 ("..., Tahun 2023"), **bukan** dari nama file.
- Pakai kolom **Total** dari sumber, jangan merata-rata Negeri dan Swasta.
- Buang baris **Luar Negeri**. Baris **Indonesia** (tanpa kode) disimpan dengan `kode_bps = 99`.

### `sumber_data`
Asal tiap dataset. Wajib diisi menurut ketentuan tugas. `etl_lokal.py` sudah mengisinya; perbarui
kalau sumber CSV dan XLSX kapasitas sudah diketahui.

| Kolom | Isi |
|---|---|
| kode | nama tabel, misal `produksi_listrik` |
| nama | judul dataset |
| format_asal | `JSON`, `CSV`, `XLSX` |
| sumber | misal `BPS, Susenas Maret` |
| url | link halaman sumber |
| keterangan | satuan / catatan |
| file_asal | nama file di `data/mentah/` |
| tahun_data | tahun data |
| data_contoh | `0` |

## Validasi yang harus lolos sebelum load

1. Setiap tabel punya 38 provinsi + 1 baris nasional, dan semua `kode_bps` ada di tabel `provinsi`.
2. Jumlah produksi 38 provinsi = baris INDONESIA (343.891,75 GWh, selisih pembulatan < 0,1).
3. Jumlah kapasitas 38 provinsi = baris INDONESIA (75.936,46 MW).
4. Semua persentase di antara 0 dan 100.
5. Tidak ada nama provinsi di CSV/XLSX yang gagal dicocokkan.

## Garis besar transformasi di Pentaho

Saran susunan step. Nama step bisa sedikit berbeda tergantung versi Pentaho.

- **provinsi + rumah tangga (JSON)**
  1. *JSON Input* membaca `$.vervar[*].val` dan `$.vervar[*].label`.
  2. *Calculator*: `kode_bps = val / 100`.
  3. Untuk nilai: *JSON Input* kedua (atau *Modified JavaScript Value*) membaca `datacontent`, lalu kunci
     dibangun dari `val + "853" + "189"/"190"/"191" + "124" + "0"`.
  4. *Value Mapper* atau rumus untuk kolom `wilayah`.
- **produksi (CSV)**: *CSV File Input* (lewati 3 baris header) → *String operations* (trim, huruf besar,
  `KEPULAUAN` → `KEP.`) → *Stream lookup* ke `provinsi` untuk mendapat `kode_bps` → *Add constants*
  `tahun = 2024`.
- **kapasitas (XLSX)**: *Microsoft Excel Input* (mulai baris 4) → *Select values* (ubah teks ke Number)
  → langkah pencocokan nama yang sama dengan CSV.
- **SMA/SMK (XLSX)**: *Microsoft Excel Input* sheet `data` (mulai baris 4) → *Filter rows* buang
  `Luar Negeri` → ganti kode kosong pada baris `Indonesia` jadi 99 → *Add constants* `tahun = 2023`.
- Semua: *Table Output* ke Supabase dengan **Truncate table** dicentang.

## Koneksi Pentaho ke Supabase

Di Pentaho: **View > Database connections > New**

| Isian | Nilai |
|---|---|
| Connection type | PostgreSQL |
| Access | Native (JDBC) |
| Host name | dari Supabase > Connect > Session pooler (contoh `aws-0-ap-southeast-1.pooler.supabase.com`) |
| Database name | `postgres` |
| Port | `5432` |
| Username | `postgres.<project-ref>` (dari Supabase) |
| Password | password database Supabase |

Tab **Options**: tambahkan parameter `sslmode` = `require`.

Tabel dibuat otomatis oleh `python seed.py` (dengan `DATABASE_URL` mengarah ke Supabase), jadi jalankan
itu dulu sebelum Pentaho.
