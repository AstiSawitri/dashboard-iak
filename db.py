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


def connect():
    if IS_PG:
        import psycopg2  # di-install lewat requirements.txt
        return psycopg2.connect(DATABASE_URL)
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

# Tabel dari versi pertama (data contoh) yang sudah tidak dipakai
TABEL_LAMA = ["konsumsi_energi", "rasio_elektrifikasi", "kapasitas_ebt", "pelanggan_listrik"]


def init_schema():
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
