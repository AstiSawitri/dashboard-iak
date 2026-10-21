"""
Lapisan akses database.

- Tanpa DATABASE_URL  -> pakai SQLite lokal (file energi.db), cocok buat ngembangin di laptop.
- DATABASE_URL=postgresql://...  -> pakai PostgreSQL (misalnya Supabase), database yang
  sama yang diisi Pentaho.

Semua query ditulis dengan placeholder "?" lalu otomatis diubah ke "%s" untuk PostgreSQL.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Baca file .env sederhana (KEY=VALUE) kalau ada, supaya tidak perlu set variabel manual di Windows
_env = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env):
    with open(_env, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    # beberapa layanan memberi awalan postgres:// (format lama)
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

IS_PG = DATABASE_URL.startswith("postgresql://")


# ---------------------------------------------------------------------------
# Mode sumber data
#   "lokal" : tabel integrasi diisi etl_lokal.py (SQLite di laptop, atau PostgreSQL kosong)
#   "dw"    : data warehouse hasil ETL Pentaho di schema `dw` (dim_* + fact_*). Web TIDAK mengubah
#             schema dw; web membuat schema `arus` berisi view jembatan dengan nama tabel yang
#             dibaca API (provinsi, rumah_tangga_listrik, ...), plus tabel users miliknya sendiri.
# Otomatis "dw" kalau PostgreSQL punya dw.dim_provinsi. Paksa lewat SUMBER_DATA=lokal / dw.
# ---------------------------------------------------------------------------
_MODE = None


def mode():
    global _MODE
    if _MODE is None:
        paksa = os.environ.get("SUMBER_DATA", "").strip().lower()
        if paksa in ("lokal", "dw"):
            _MODE = paksa
        elif not IS_PG:
            _MODE = "lokal"
        else:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            try:
                cur = conn.cursor()
                cur.execute("SELECT to_regclass('dw.dim_provinsi') IS NOT NULL")
                _MODE = "dw" if cur.fetchone()[0] else "lokal"
            finally:
                conn.close()
    return _MODE


def connect():
    if IS_PG:
        import psycopg2  # di-install lewat requirements.txt
        conn = psycopg2.connect(DATABASE_URL)
        if mode() == "dw":
            cur = conn.cursor()
            cur.execute("SET search_path TO arus, public")
        return conn
    path = os.environ.get("SQLITE_PATH", os.path.join(BASE_DIR, "energi.db"))
    conn = sqlite3.connect(path)
    return conn


def _sql(q):
    return q.replace("?", "%s") if IS_PG else q


def query(q, params=()):
    """Jalankan SELECT, hasilnya list of dict."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(_sql(q), params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def execute(q, params=()):
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(_sql(q), params)
        conn.commit()
    finally:
        conn.close()


def executemany(q, rows):
    conn = connect()
    try:
        cur = conn.cursor()
        cur.executemany(_sql(q), rows)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Skema. Nama tabel & kolom ini adalah "kontrak" dengan hasil ETL (Pentaho atau etl_lokal.py).
# Lihat SKEMA_DATA.md.
#
# Semua tabel fakta terhubung ke tabel `provinsi` lewat kode_bps (11 = Aceh, ..., 97 = Papua Pegunungan).
# Baris nasional (INDONESIA) disimpan dengan kode_bps = 99.
# ---------------------------------------------------------------------------
SERIAL = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
NUM = "DOUBLE PRECISION"

SCHEMA = [
    f"""CREATE TABLE IF NOT EXISTS users (
        id {SERIAL},
        username VARCHAR(50) UNIQUE NOT NULL,
        nama VARCHAR(100) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        dibuat_pada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS provinsi (
        kode_bps INTEGER PRIMARY KEY,
        nama VARCHAR(60) NOT NULL,
        wilayah VARCHAR(40) NOT NULL
    )""",
    f"""CREATE TABLE IF NOT EXISTS rumah_tangga_listrik (
        kode_bps INTEGER NOT NULL,
        tahun INTEGER NOT NULL,
        perkotaan_persen {NUM},
        perdesaan_persen {NUM},
        total_persen {NUM},
        PRIMARY KEY (kode_bps, tahun)
    )""",
    f"""CREATE TABLE IF NOT EXISTS produksi_listrik (
        kode_bps INTEGER NOT NULL,
        tahun INTEGER NOT NULL,
        produksi_gwh {NUM},
        PRIMARY KEY (kode_bps, tahun)
    )""",
    f"""CREATE TABLE IF NOT EXISTS kapasitas_pembangkit (
        kode_bps INTEGER NOT NULL,
        tahun INTEGER NOT NULL,
        kapasitas_mw {NUM},
        PRIMARY KEY (kode_bps, tahun)
    )""",
    f"""CREATE TABLE IF NOT EXISTS sma_listrik (
        kode_bps INTEGER NOT NULL,
        tahun INTEGER NOT NULL,
        negeri_persen {NUM},
        swasta_persen {NUM},
        total_persen {NUM},
        PRIMARY KEY (kode_bps, tahun)
    )""",
    f"""CREATE TABLE IF NOT EXISTS smk_listrik (
        kode_bps INTEGER NOT NULL,
        tahun INTEGER NOT NULL,
        negeri_persen {NUM},
        swasta_persen {NUM},
        total_persen {NUM},
        PRIMARY KEY (kode_bps, tahun)
    )""",
    """CREATE TABLE IF NOT EXISTS sumber_data (
        kode VARCHAR(40) PRIMARY KEY,
        nama VARCHAR(160) NOT NULL,
        format_asal VARCHAR(10) NOT NULL,
        sumber VARCHAR(200) NOT NULL,
        url VARCHAR(300),
        keterangan VARCHAR(300),
        file_asal VARCHAR(200),
        tahun_data INTEGER,
        data_contoh INTEGER DEFAULT 0
    )""",
]

# ---------------------------------------------------------------------------
# TIGA LEVEL DATA
#   1. STAGING     stg_*      salinan mentah tiap file, semua kolom teks, apa adanya (duplikasi)
#   2. INTEGRASI   provinsi, rumah_tangga_listrik, ...   data bersih & seragam (hasil transformasi)
#   3. PRESENTASI  v_provinsi_lengkap   view gabungan 5 dataset yang dibaca web/API
# Sinkronisasi dicatat di etl_batch + etl_log (hash file sumber dipakai untuk deteksi perubahan).
# ---------------------------------------------------------------------------
TXT = "TEXT"
SCHEMA += [
    # level 1: staging (isi file disalin baris per baris tanpa diubah)
    f"""CREATE TABLE IF NOT EXISTS stg_rumah_tangga_listrik (
        batch_id INTEGER, kode_wilayah {TXT}, nama_wilayah {TXT}, klasifikasi {TXT}, tahun {TXT}, nilai {TXT}
    )""",
    f"""CREATE TABLE IF NOT EXISTS stg_produksi_listrik (
        batch_id INTEGER, baris_ke INTEGER, kolom_1 {TXT}, kolom_2 {TXT}
    )""",
    f"""CREATE TABLE IF NOT EXISTS stg_kapasitas_pembangkit (
        batch_id INTEGER, baris_ke INTEGER, kolom_1 {TXT}, kolom_2 {TXT}
    )""",
    f"""CREATE TABLE IF NOT EXISTS stg_sma_listrik (
        batch_id INTEGER, baris_ke INTEGER, kolom_1 {TXT}, kolom_2 {TXT}, kolom_3 {TXT}, kolom_4 {TXT},
        kolom_5 {TXT}, kolom_6 {TXT}, kolom_7 {TXT}
    )""",
    f"""CREATE TABLE IF NOT EXISTS stg_smk_listrik (
        batch_id INTEGER, baris_ke INTEGER, kolom_1 {TXT}, kolom_2 {TXT}, kolom_3 {TXT}, kolom_4 {TXT},
        kolom_5 {TXT}, kolom_6 {TXT}, kolom_7 {TXT}
    )""",
    # catatan sinkronisasi
    f"""CREATE TABLE IF NOT EXISTS etl_batch (
        batch_id {SERIAL},
        alat VARCHAR(30) NOT NULL,
        mulai TIMESTAMP NOT NULL,
        selesai TIMESTAMP,
        status VARCHAR(20) NOT NULL,
        catatan VARCHAR(300)
    )""",
    f"""CREATE TABLE IF NOT EXISTS etl_log (
        id {SERIAL},
        batch_id INTEGER NOT NULL,
        waktu TIMESTAMP NOT NULL,
        tingkat VARCHAR(12) NOT NULL,
        dataset VARCHAR(40) NOT NULL,
        file_asal VARCHAR(200),
        hash_file VARCHAR(64),
        baris INTEGER,
        status VARCHAR(20) NOT NULL,
        pesan VARCHAR(300)
    )""",
]

# level 3: presentasi. View dibuat ulang tiap start supaya selalu sesuai skema.
VIEWS = {
    "v_provinsi_lengkap": """
SELECT p.kode_bps, p.nama AS provinsi, p.wilayah,
       pr.tahun AS produksi_tahun, pr.produksi_gwh,
       kp.tahun AS kapasitas_tahun, kp.kapasitas_mw,
       rt.tahun AS rt_tahun, rt.total_persen AS rumah_tangga_persen,
       rt.perkotaan_persen AS rumah_tangga_kota_persen, rt.perdesaan_persen AS rumah_tangga_desa_persen,
       sma.tahun AS sma_tahun, sma.negeri_persen AS sma_negeri_persen, sma.swasta_persen AS sma_swasta_persen,
       sma.total_persen AS sma_persen,
       smk.tahun AS smk_tahun, smk.negeri_persen AS smk_negeri_persen, smk.swasta_persen AS smk_swasta_persen,
       smk.total_persen AS smk_persen
FROM provinsi p
LEFT JOIN produksi_listrik pr     ON pr.kode_bps = p.kode_bps
LEFT JOIN kapasitas_pembangkit kp ON kp.kode_bps = p.kode_bps
LEFT JOIN rumah_tangga_listrik rt ON rt.kode_bps = p.kode_bps
LEFT JOIN sma_listrik sma         ON sma.kode_bps = p.kode_bps
LEFT JOIN smk_listrik smk         ON smk.kode_bps = p.kode_bps
""",
}

STAGING = ["stg_rumah_tangga_listrik", "stg_produksi_listrik", "stg_kapasitas_pembangkit", "stg_sma_listrik", "stg_smk_listrik"]

# Tabel dari versi pertama (data contoh) yang sudah tidak dipakai
TABEL_LAMA = ["konsumsi_energi", "rasio_elektrifikasi", "kapasitas_ebt", "pelanggan_listrik"]


# Jembatan ke data warehouse Pentaho (schema dw). Dibaca sebagai tabel integrasi oleh web.
_WILAYAH = """CASE WHEN CAST(p.kode_bps AS INTEGER) = 99 THEN 'Nasional'
             WHEN CAST(p.kode_bps AS INTEGER) < 30 THEN 'Sumatera'
             WHEN CAST(p.kode_bps AS INTEGER) < 40 THEN 'Jawa'
             WHEN CAST(p.kode_bps AS INTEGER) < 60 THEN 'Bali dan Nusa Tenggara'
             WHEN CAST(p.kode_bps AS INTEGER) < 70 THEN 'Kalimantan'
             WHEN CAST(p.kode_bps AS INTEGER) < 80 THEN 'Sulawesi'
             WHEN CAST(p.kode_bps AS INTEGER) < 90 THEN 'Maluku'
             ELSE 'Papua' END"""
_PROV = "dw.dim_provinsi p ON p.provinsi_key = f.provinsi_key AND p.tipe_wilayah IN ('PROVINSI', 'NASIONAL')"


def _sekolah_dw(jenjang):
    return f"""
SELECT CAST(p.kode_bps AS INTEGER) AS kode_bps, CAST(t.tahun AS INTEGER) AS tahun,
       CAST(MAX(CASE WHEN s.nama = 'Negeri' THEN f.persen_akses END) AS DOUBLE PRECISION) AS negeri_persen,
       CAST(MAX(CASE WHEN s.nama = 'Swasta' THEN f.persen_akses END) AS DOUBLE PRECISION) AS swasta_persen,
       CAST(MAX(CASE WHEN s.is_total THEN f.persen_akses END) AS DOUBLE PRECISION) AS total_persen
FROM dw.fact_akses_listrik_sekolah f
JOIN {_PROV}
JOIN dw.dim_tahun t ON t.tahun_key = f.tahun_key
JOIN dw.dim_jenjang_sekolah j ON j.jenjang_key = f.jenjang_key AND j.kode = '{jenjang}'
JOIN dw.dim_status_sekolah s ON s.status_key = f.status_key
GROUP BY p.kode_bps, t.tahun"""


DW_JEMBATAN = {
    "provinsi": f"""
SELECT CAST(p.kode_bps AS INTEGER) AS kode_bps, p.nama_standar AS nama, {_WILAYAH} AS wilayah
FROM dw.dim_provinsi p
WHERE p.tipe_wilayah IN ('PROVINSI', 'NASIONAL') AND p.kode_bps IS NOT NULL""",
    "rumah_tangga_listrik": f"""
SELECT CAST(p.kode_bps AS INTEGER) AS kode_bps, CAST(t.tahun AS INTEGER) AS tahun,
       CAST(MAX(CASE WHEN k.nama = 'Perkotaan' THEN f.persen_rt END) AS DOUBLE PRECISION) AS perkotaan_persen,
       CAST(MAX(CASE WHEN k.nama = 'Perdesaan' THEN f.persen_rt END) AS DOUBLE PRECISION) AS perdesaan_persen,
       CAST(MAX(CASE WHEN k.is_gabungan THEN f.persen_rt END) AS DOUBLE PRECISION) AS total_persen
FROM dw.fact_akses_listrik_rt f
JOIN {_PROV}
JOIN dw.dim_tahun t ON t.tahun_key = f.tahun_key
JOIN dw.dim_klasifikasi_wilayah k ON k.klasifikasi_key = f.klasifikasi_key
GROUP BY p.kode_bps, t.tahun""",
    "produksi_listrik": f"""
SELECT CAST(p.kode_bps AS INTEGER) AS kode_bps, CAST(t.tahun AS INTEGER) AS tahun,
       CAST(f.energi_gwh AS DOUBLE PRECISION) AS produksi_gwh
FROM dw.fact_listrik_dibangkitkan f JOIN {_PROV} JOIN dw.dim_tahun t ON t.tahun_key = f.tahun_key""",
    "kapasitas_pembangkit": f"""
SELECT CAST(p.kode_bps AS INTEGER) AS kode_bps, CAST(t.tahun AS INTEGER) AS tahun,
       CAST(f.kapasitas_mw AS DOUBLE PRECISION) AS kapasitas_mw
FROM dw.fact_kapasitas_pembangkit f JOIN {_PROV} JOIN dw.dim_tahun t ON t.tahun_key = f.tahun_key""",
    "sma_listrik": _sekolah_dw("SMA"),
    "smk_listrik": _sekolah_dw("SMK"),
    "sumber_data": """
SELECT CASE d.kode_dataset WHEN 'RT_LISTRIK' THEN 'rumah_tangga_listrik' WHEN 'GWH' THEN 'produksi_listrik'
            WHEN 'KAPASITAS' THEN 'kapasitas_pembangkit' WHEN 'SMA' THEN 'sma_listrik'
            WHEN 'SMK' THEN 'smk_listrik' ELSE LOWER(d.kode_dataset) END AS kode,
       d.nama_dataset AS nama, d.format_file AS format_asal,
       CASE WHEN d.kode_dataset IN ('GWH', 'KAPASITAS') THEN COALESCE(d.sumber, 'Badan Pusat Statistik (BPS)')
            WHEN d.kode_dataset IN ('SMA', 'SMK') THEN 'Satu Data, Pusdatin Kementerian Pendidikan Dasar dan Menengah'
            ELSE COALESCE(d.sumber, 'Badan Pusat Statistik (BPS)') END AS sumber,
       CASE WHEN d.kode_dataset IN ('GWH', 'KAPASITAS', 'RT_LISTRIK') THEN 'https://www.bps.go.id'
            ELSE '' END AS url,
       CASE WHEN d.satuan = 'Persen' THEN 'Persen' ELSE COALESCE(d.satuan, '') END AS keterangan,
       d.nama_file AS file_asal,
       CAST(SUBSTRING(d.periode_di_file FROM '[0-9]{4}') AS INTEGER) AS tahun_data,
       0 AS data_contoh
FROM dw.dim_dataset d""",
}


def _init_dw():
    execute("CREATE SCHEMA IF NOT EXISTS arus")
    for nama in list(VIEWS) + list(DW_JEMBATAN):
        execute(f"DROP VIEW IF EXISTS arus.{nama} CASCADE")
    for nama, sql in DW_JEMBATAN.items():
        execute(f"CREATE VIEW arus.{nama} AS {sql}")
    execute(SCHEMA[0])                       # cukup tabel users; data, staging, dan log milik Pentaho
    for nama, sql in VIEWS.items():
        execute(f"CREATE VIEW {nama} AS {sql}")


def init_schema():
    if mode() == "dw":
        return _init_dw()
    # Bersihkan sisa versi pertama (data contoh) yang strukturnya berbeda
    if "jenis_pembangkit" in (_kolom("produksi_listrik") or []):
        execute("DROP TABLE produksi_listrik")
    cols = _kolom("sumber_data")
    if cols is not None and "file_asal" not in cols:
        execute("DROP TABLE sumber_data")
    for t in TABEL_LAMA:
        execute(f"DROP TABLE IF EXISTS {t}")
    for stmt in SCHEMA:
        execute(stmt)
    for nama, sql in VIEWS.items():
        execute(f"DROP VIEW IF EXISTS {nama}")
        execute(f"CREATE VIEW {nama} AS {sql}")


def _kolom(tabel):
    """Daftar kolom sebuah tabel, atau None kalau tabelnya belum ada."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {tabel} WHERE 1=0")
        return [c[0].lower() for c in cur.description]
    except Exception:
        return None
    finally:
        conn.close()
