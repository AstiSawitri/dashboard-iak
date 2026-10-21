"""
ARUS, dasbor kelistrikan Indonesia
Tugas Integrasi Aplikasi Korporasi (EAI)

Tiga lapisan (three-tier):
  1. User interface  -> templates/ + static/ (HTML, CSS, Chart.js)
  2. Business logic  -> file ini (Flask: login, API, ringkasan)
  3. Data            -> database (SQLite lokal / PostgreSQL Supabase) yang diisi ETL
                        (Pentaho, atau etl_lokal.py sebagai cadangan)
"""
import csv
import io
import os
from functools import wraps

from flask import (Flask, Response, abort, flash, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ganti-ini-di-production")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.json.sort_keys = False  # pertahankan urutan kolom

ALLOW_REGISTER = os.environ.get("ALLOW_REGISTER", "1") == "1"

# Daftar dataset yang boleh diakses lewat API (whitelist, supaya aman dari SQL injection).
DATASETS = {
    "rumah_tangga_listrik": {
        "judul": "Rumah tangga dengan penerangan utama dari listrik",
        "kolom": ["perkotaan_persen", "perdesaan_persen", "total_persen"],
    },
    "produksi_listrik": {
        "judul": "Tenaga listrik yang dibangkitkan",
        "kolom": ["produksi_gwh"],
    },
    "kapasitas_pembangkit": {
        "judul": "Kapasitas terpasang pembangkit listrik",
        "kolom": ["kapasitas_mw"],
    },
    "sma_listrik": {
        "judul": "SMA yang memiliki akses listrik",
        "kolom": ["negeri_persen", "swasta_persen", "total_persen"],
    },
    "smk_listrik": {
        "judul": "SMK yang memiliki akses listrik",
        "kolom": ["negeri_persen", "swasta_persen", "total_persen"],
    },
}
NASIONAL = 99
JAM_SETAHUN = 8760  # 365 x 24, untuk perkiraan faktor kapasitas


# ---------------------------------------------------------------------------
# Autentikasi
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith(("/api/", "/atlas/api/")):
                return jsonify({"error": "Silakan masuk dulu."}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))


@app.route("/masuk", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        rows = db.query("SELECT id, nama, password_hash FROM users WHERE username = ?", (username,))
        if rows and check_password_hash(rows[0]["password_hash"], password):
            session.clear()
            session["user_id"] = rows[0]["id"]
            session["nama"] = rows[0]["nama"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Username atau kata sandi salah.")
    return render_template("login.html", allow_register=ALLOW_REGISTER)


@app.route("/daftar", methods=["GET", "POST"])
def register():
    if not ALLOW_REGISTER:
        abort(404)
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not nama or not username or len(password) < 6:
            flash("Isi semua kolom. Kata sandi minimal 6 karakter.")
        elif db.query("SELECT id FROM users WHERE username = ?", (username,)):
            flash("Username itu sudah dipakai. Coba yang lain.")
        else:
            db.execute(
                "INSERT INTO users (username, nama, password_hash) VALUES (?, ?, ?)",
                (username, nama, generate_password_hash(password)),
            )
            flash("Akun dibuat. Silakan masuk.")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/keluar")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Halaman
# ---------------------------------------------------------------------------
@app.route("/dasbor")
@login_required
def dashboard():
    return render_template("dashboard.html", page="dasbor")


@app.route("/data")
@login_required
def data_page():
    return render_template("data.html", page="data", datasets=DATASETS)


# ---------------------------------------------------------------------------
# API (Application Interface-level)
# ---------------------------------------------------------------------------
def _filter_provinsi(args, alias="p"):
    """Filter wilayah / provinsi. Baris nasional (kode 99) ikut hanya kalau ?nasional=1."""
    where, params = [], []
    if args.get("nasional") != "1":
        where.append(f"{alias}.kode_bps <> ?")
        params.append(NASIONAL)
    if args.get("wilayah"):
        where.append(f"{alias}.wilayah = ?")
        params.append(args["wilayah"])
    if args.get("kode"):
        where.append(f"{alias}.kode_bps = ?")
        params.append(int(args["kode"]))
    return where, params


def _fetch(name, args):
    meta = DATASETS.get(name)
    if not meta:
        abort(404)
    where, params = _filter_provinsi(args)
    kolom = ", ".join(f"t.{k}" for k in meta["kolom"])
    q = (f"SELECT p.kode_bps, p.nama AS provinsi, p.wilayah, t.tahun, {kolom} "
         f"FROM {name} t JOIN provinsi p ON p.kode_bps = t.kode_bps")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY p.kode_bps"
    return meta, db.query(q, tuple(params))


@app.route("/api/data/<name>")
@login_required
def api_data(name):
    meta, rows = _fetch(name, request.args)
    return jsonify({"dataset": name, "judul": meta["judul"], "jumlah": len(rows), "data": rows})


@app.route("/api/data/<name>.csv")
@login_required
def api_data_csv(name):
    _, rows = _fetch(name, request.args)
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}.csv"})


# Level presentasi: view v_provinsi_lengkap (dibuat di db.py) sudah menggabungkan kelima dataset.
GABUNGAN_SQL = """
SELECT p.kode_bps, p.provinsi, p.wilayah, p.produksi_gwh, p.kapasitas_mw,
       p.rumah_tangga_persen, p.rumah_tangga_kota_persen, p.rumah_tangga_desa_persen,
       p.sma_persen, p.smk_persen
FROM v_provinsi_lengkap p
"""


def _gabungan(args):
    where, params = _filter_provinsi(args)
    q = GABUNGAN_SQL + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY p.kode_bps"
    rows = db.query(q, tuple(params))
    for r in rows:
        # Logika bisnis: indikator turunan dari gabungan dataset
        gwh, mw = r["produksi_gwh"], r["kapasitas_mw"]
        r["faktor_kapasitas_persen"] = round(gwh * 1000 / (mw * JAM_SETAHUN) * 100, 1) if gwh and mw else None
        kota, desa = r["rumah_tangga_kota_persen"], r["rumah_tangga_desa_persen"]
        r["selisih_kota_desa_poin"] = round(kota - desa, 2) if kota is not None and desa is not None else None
    return rows


@app.route("/api/gabungan")
@login_required
def api_gabungan():
    """Satu baris per provinsi, kelima dataset digabung lewat kode_bps."""
    rows = _gabungan(request.args)
    return jsonify({"jumlah": len(rows), "data": rows})


@app.route("/api/meta")
@login_required
def api_meta():
    provinsi = db.query("SELECT kode_bps, nama, wilayah FROM provinsi WHERE kode_bps <> ? ORDER BY kode_bps",
                        (NASIONAL,))
    wilayah = []
    for p in provinsi:
        if p["wilayah"] not in wilayah:
            wilayah.append(p["wilayah"])
    urut = list(DATASETS)
    sumber = sorted(db.query("SELECT * FROM sumber_data"),
                    key=lambda s: urut.index(s["kode"]) if s["kode"] in urut else 99)
    for s in sumber:
        if s["kode"] in DATASETS:
            s["jumlah_baris"] = db.query(f"SELECT COUNT(*) AS n FROM {s['kode']}")[0]["n"]
    return jsonify({
        "provinsi": provinsi,
        "wilayah": wilayah,
        "sumber": sumber,
        "data_contoh": any(s.get("data_contoh") for s in sumber),
    })


INDIKATOR = ["produksi_gwh", "kapasitas_mw", "rumah_tangga_persen", "rumah_tangga_desa_persen",
             "sma_persen", "smk_persen", "faktor_kapasitas_persen"]


@app.route("/api/etl")
@login_required
def api_etl():
    """Riwayat sinkronisasi dan jumlah baris di tiap level data."""
    batch = db.query("SELECT * FROM etl_batch ORDER BY batch_id DESC LIMIT 10")
    log = db.query("SELECT * FROM etl_log ORDER BY id DESC LIMIT 40")
    level = []
    for ds in DATASETS:
        stg = db.query(f"SELECT COUNT(*) AS n FROM stg_{ds}")[0]["n"]
        integ = db.query(f"SELECT COUNT(*) AS n FROM {ds}")[0]["n"]
        level.append({"dataset": ds, "staging": stg, "integrasi": integ})
    pres = db.query("SELECT COUNT(*) AS n FROM v_provinsi_lengkap")[0]["n"]
    for x in batch + log:
        for k in ("mulai", "selesai", "waktu"):
            if x.get(k) is not None:
                x[k] = str(x[k])[:19]
    return jsonify({"batch": batch, "log": log, "level": level, "presentasi": pres})


@app.route("/api/ringkasan")
@login_required
def api_ringkasan():
    """Angka utama: nasional, atau satu provinsi beserta peringkatnya di antara 38 provinsi."""
    kode = request.args.get("kode", type=int)
    semua = _gabungan({})
    nas = _gabungan({"nasional": "1", "kode": str(NASIONAL)})
    if nas:
        nas = nas[0]
    else:
        nas = {k: None for k in INDIKATOR}
    if not kode:
        return jsonify({"lingkup": "nasional", "nilai": nas, "jumlah_provinsi": len(semua)})
    baris = next((r for r in semua if r["kode_bps"] == kode), None)
    if not baris:
        abort(404)
    peringkat = {}
    for k in INDIKATOR:
        nilai = [r[k] for r in semua if r[k] is not None]
        if baris[k] is not None:
            peringkat[k] = 1 + sum(1 for v in nilai if v > baris[k])
    return jsonify({"lingkup": "provinsi", "nilai": baris, "nasional": nas,
                    "peringkat": peringkat, "jumlah_provinsi": len(semua)})


# ---------------------------------------------------------------------------
# Atlas: dashboard buatan anggota kelompok (prototipe ARUS), dipasang di web ini.
# Tampilannya tetap milik ARUS (static/atlas/), tapi datanya diambil dari database
# web ini lewat API di bawah. Format JSON-nya dibuat sama persis dengan server Java ARUS,
# jadi kode grafiknya tidak perlu diubah. Ini contoh Application Interface-level EAI.
# ---------------------------------------------------------------------------
ATLAS_SQL = """
SELECT kode_bps, provinsi AS nama, wilayah,
       rt_tahun, rumah_tangga_persen AS rt_total, rumah_tangga_kota_persen AS rt_kota, rumah_tangga_desa_persen AS rt_desa,
       produksi_gwh, kapasitas_mw,
       sma_tahun, sma_negeri_persen AS sma_negeri, sma_swasta_persen AS sma_swasta, sma_persen AS sma_total,
       smk_tahun, smk_negeri_persen AS smk_negeri, smk_swasta_persen AS smk_swasta, smk_persen AS smk_total
FROM v_provinsi_lengkap
ORDER BY kode_bps
"""


def _format_arus(r):
    nasional = r["kode_bps"] == NASIONAL
    return {
        "code": "9999" if nasional else str(r["kode_bps"] * 100),
        "name": r["nama"],
        "region": "Indonesia" if nasional else r["wilayah"],
        "energyYear": r["rt_tahun"],
        "householdTotalPct": r["rt_total"],
        "householdUrbanPct": r["rt_kota"],
        "householdRuralPct": r["rt_desa"],
        "generationGwh": r["produksi_gwh"],
        "capacityMw": r["kapasitas_mw"],
        "smaYear": r["sma_tahun"],
        "smaPublicPct": r["sma_negeri"],
        "smaPrivatePct": r["sma_swasta"],
        "smaTotalPct": r["sma_total"],
        "smkYear": r["smk_tahun"],
        "smkPublicPct": r["smk_negeri"],
        "smkPrivatePct": r["smk_swasta"],
        "smkTotalPct": r["smk_total"],
    }


@app.route("/atlas")
@login_required
def atlas():
    return render_template("atlas.html")


@app.route("/atlas/api/session")
@login_required
def atlas_session():
    return jsonify({"user": session.get("nama"), "csrf": ""})


@app.route("/atlas/api/data")
@login_required
def atlas_data():
    rows = [_format_arus(r) for r in db.query(ATLAS_SQL)]
    sumber = db.query("SELECT * FROM sumber_data")
    return jsonify({
        "title": "ARUS - Dashboard Kelistrikan Indonesia",
        "provinces": [r for r in rows if r["code"] != "9999"],
        "national": next((r for r in rows if r["code"] == "9999"), {}),
        "sources": [{"file": s["file_asal"], "format": s["format_asal"], "year": s["tahun_data"],
                     "unit": s["keterangan"], "publisher": s["sumber"]} for s in sumber],
        "methodology": [],
    })


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Tidak ditemukan."}), 404
    return render_template("404.html"), 404


# Buat tabel kalau belum ada (aman dijalankan berulang kali)
db.init_schema()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
