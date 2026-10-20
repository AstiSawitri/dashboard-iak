"""
ETL lokal: memuat 5 file mentah di data/mentah/ ke database.

    python etl_lokal.py

Alur yang sama seharusnya dikerjakan di Pentaho (lihat SKEMA_DATA.md). Skrip ini dipakai
sebagai cadangan dan pembanding: kalau hasil Pentaho benar, isi tabelnya sama persis dengan
hasil skrip ini.

  EXTRACT    baca JSON (BPS), CSV, dan 3 XLSX
  TRANSFORM  samakan nama/kode provinsi, ubah bentuk data, ubah teks jadi angka,
             buang baris judul/total/Luar Negeri, cek kelengkapan & total nasional
  LOAD       kosongkan tabel tujuan lalu isi ulang (truncate + insert)
"""
import json
import os
import re
import sys

import db

MENTAH = os.path.join(db.BASE_DIR, "data", "mentah")
FILE = {
    "rumah_tangga_listrik": "rumah_tangga_listrik_2024.json",
    "produksi_listrik": "produksi_listrik_2024.csv",
    "kapasitas_pembangkit": "kapasitas_pembangkit_2024.xlsx",
    "sma_listrik": "sma_akses_listrik.xlsx",
    "smk_listrik": "smk_akses_listrik.xlsx",
}
NASIONAL = 99


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- bantuan transform
def normal(nama):
    """Kunci pencocokan nama provinsi: huruf besar, 'KEP.' disamakan, spasi dirapikan."""
    s = str(nama).replace("﻿", "").strip().upper()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("KEPULAUAN ", "KEP. ")
    s = s.replace("DAERAH ISTIMEWA YOGYAKARTA", "DI YOGYAKARTA")
    return s


def nama_tampil(label):
    khusus = {"DKI JAKARTA": "DKI Jakarta", "DI YOGYAKARTA": "DI Yogyakarta", "INDONESIA": "Indonesia"}
    if label in khusus:
        return khusus[label]
    label = label.replace("KEP. ", "KEPULAUAN ")
    return " ".join(w.capitalize() for w in label.lower().split())


def wilayah(kode):
    if kode == NASIONAL:
        return "Nasional"
    for batas, nama in ((30, "Sumatera"), (40, "Jawa"), (60, "Bali dan Nusa Tenggara"),
                        (70, "Kalimantan"), (80, "Sulawesi"), (90, "Maluku"), (99, "Papua")):
        if kode < batas:
            return nama
    return "Lainnya"


def angka(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "…", "..."):
        return None
    return float(s.replace(",", "."))


def baca_xlsx(path, sheet=None):
    from openpyxl import load_workbook  # pip install openpyxl
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True)]


# ---------------------------------------------------------------- extract + transform
def rumah_tangga(path):
    """JSON tabel dinamis BPS: kunci datacontent = kode wilayah + var + turvar + tahun + turtahun."""
    raw = json.load(open(path, encoding="utf-8"))
    var = str(raw["var"][0]["val"])
    th = raw["tahun"][0]
    kode_tahun, tahun = str(th["val"]), int(th["label"])
    turtahun = str(raw["turtahun"][0]["val"])
    turvar = {t["label"]: str(t["val"]) for t in raw["turvar"]}
    isi = raw["datacontent"]
    provinsi, baris = [], []
    for v in raw["vervar"]:
        kode4 = str(v["val"])
        kode = int(v["val"]) // 100
        def ambil(lbl):
            return angka(isi.get(kode4 + var + turvar[lbl] + kode_tahun + turtahun))
        provinsi.append((kode, nama_tampil(v["label"]), wilayah(kode)))
        baris.append((kode, tahun, ambil("Perkotaan"), ambil("Perdesaan"), ambil("Perkotaan+Perdesaan")))
    return provinsi, baris, tahun


def tabel_dua_kolom(rows, peta_nama):
    """Untuk CSV/XLSX ekspor BPS: kolom A nama provinsi, kolom B nilai; 3 baris pertama judul."""
    tahun = None
    hasil, tak_cocok = [], []
    for r in rows:
        if len(r) < 2 or r[0] in (None, ""):
            if len(r) > 1 and r[1] and re.fullmatch(r"\d{4}", str(r[1]).strip()):
                tahun = int(str(r[1]).strip())
            continue
        kode = peta_nama.get(normal(r[0]))
        nilai = angka(r[1])
        if kode is None:
            if nilai is not None:
                tak_cocok.append(r[0])
            continue
        hasil.append((kode, nilai))
    return hasil, tahun, tak_cocok


def sekolah(path, kode_valid):
    rows = baca_xlsx(path, "data")
    judul = str(rows[0][0])
    m = re.search(r"Tahun\s+(\d{4})", judul)
    tahun = int(m.group(1)) if m else None
    hasil = []
    for r in rows:
        if len(r) < 7:
            continue
        if normal(r[3] or "") == "INDONESIA":
            kode = NASIONAL
        elif isinstance(r[2], (int, float)):
            kode = int(r[2])          # pakai Kode BPS, bukan Kode Kemdagri (beda untuk Papua)
        else:
            continue                  # baris judul & "Luar Negeri" (tanpa kode) dibuang
        if kode not in kode_valid:
            continue
        hasil.append((kode, tahun, angka(r[4]), angka(r[5]), angka(r[6])))
    return hasil, tahun, judul


# ---------------------------------------------------------------- validasi
def cek(kondisi, pesan, masalah):
    if not kondisi:
        masalah.append(pesan)


def main():
    db.init_schema()
    masalah = []
    log("EXTRACT + TRANSFORM")

    # 1. JSON -> provinsi + rumah tangga
    prov, rt, tahun_energi = rumah_tangga(os.path.join(MENTAH, FILE["rumah_tangga_listrik"]))
    kode_valid = {p[0] for p in prov}
    peta_nama = {normal(p[1]): p[0] for p in prov}
    log(f"  JSON  rumah tangga        : {len(rt)} baris (38 provinsi + nasional), tahun {tahun_energi}")
    kosong = [p[1] for p, r in zip(prov, rt) if None in r[2:]]
    if kosong:
        log(f"        nilai kosong (dibiarkan NULL, bukan 0): {', '.join(kosong)}")

    # 2. CSV -> produksi
    import csv
    with open(os.path.join(MENTAH, FILE["produksi_listrik"]), encoding="utf-8-sig", newline="") as f:
        produksi, th_csv, tak1 = tabel_dua_kolom(list(csv.reader(f)), peta_nama)
    log(f"  CSV   produksi listrik    : {len(produksi)} baris, tahun {th_csv}")

    # 3. XLSX -> kapasitas
    kapasitas, th_kap, tak2 = tabel_dua_kolom(baca_xlsx(os.path.join(MENTAH, FILE["kapasitas_pembangkit"])), peta_nama)
    log(f"  XLSX  kapasitas pembangkit: {len(kapasitas)} baris, tahun {th_kap}")

    # 4-5. XLSX sekolah
    sma, th_sma, judul_sma = sekolah(os.path.join(MENTAH, FILE["sma_listrik"]), kode_valid)
    smk, th_smk, judul_smk = sekolah(os.path.join(MENTAH, FILE["smk_listrik"]), kode_valid)
    log(f"  XLSX  SMA berlistrik      : {len(sma)} baris, tahun {th_sma} (dari judul, bukan nama file)")
    log(f"  XLSX  SMK berlistrik      : {len(smk)} baris, tahun {th_smk} (dari judul, bukan nama file)")

    # validasi
    log("VALIDASI")
    for nama, rows in (("rumah tangga", rt), ("produksi", produksi), ("kapasitas", kapasitas), ("SMA", sma), ("SMK", smk)):
        kode_ada = {r[0] for r in rows}
        cek(kode_ada == kode_valid, f"{nama}: provinsi tidak lengkap, kurang {sorted(kode_valid - kode_ada)}", masalah)
    for nama, tak in (("produksi", tak1), ("kapasitas", tak2)):
        cek(not tak, f"{nama}: nama provinsi tidak dikenali: {tak}", masalah)
    for nama, rows in (("produksi", produksi), ("kapasitas", kapasitas)):
        nas = next((v for k, v in rows if k == NASIONAL), None)
        jumlah = sum(v for k, v in rows if k != NASIONAL and v is not None)
        cek(nas is not None and abs(jumlah - nas) < 0.1,
            f"{nama}: jumlah 38 provinsi {jumlah:.2f} tidak sama dengan baris INDONESIA {nas}", masalah)
        log(f"  {nama:<10} jumlah 38 provinsi = {jumlah:,.2f}, baris INDONESIA = {nas:,.2f}")
    for nama, rows in (("rumah tangga", rt), ("SMA", sma), ("SMK", smk)):
        for r in rows:
            for v in r[2:]:
                cek(v is None or 0 <= v <= 100, f"{nama}: persentase di luar 0-100 pada kode {r[0]}", masalah)
    if masalah:
        log("GAGAL. Tidak ada yang dimuat ke database:")
        for m in masalah:
            log("  - " + m)
        sys.exit(1)
    log("  semua cek lolos")

    # load
    log("LOAD")
    muat = [
        ("provinsi", "INSERT INTO provinsi (kode_bps, nama, wilayah) VALUES (?, ?, ?)", prov),
        ("rumah_tangga_listrik", "INSERT INTO rumah_tangga_listrik VALUES (?, ?, ?, ?, ?)", rt),
        ("produksi_listrik", "INSERT INTO produksi_listrik VALUES (?, ?, ?)", [(k, th_csv, v) for k, v in produksi]),
        ("kapasitas_pembangkit", "INSERT INTO kapasitas_pembangkit VALUES (?, ?, ?)", [(k, th_kap, v) for k, v in kapasitas]),
        ("sma_listrik", "INSERT INTO sma_listrik VALUES (?, ?, ?, ?, ?)", sma),
        ("smk_listrik", "INSERT INTO smk_listrik VALUES (?, ?, ?, ?, ?)", smk),
    ]
    for tabel, sql, rows in muat:
        db.execute(f"DELETE FROM {tabel}")
        db.executemany(sql, rows)
        log(f"  {tabel:<22} {len(rows)} baris")

    url_bps = "https://www.bps.go.id/id/statistics-table?subject=558"
    sumber = [
        ("rumah_tangga_listrik", "Persentase rumah tangga dengan sumber penerangan utama dari listrik, menurut provinsi dan klasifikasi desa",
         "JSON", "BPS, Susenas Maret", url_bps, "Persen rumah tangga", FILE["rumah_tangga_listrik"], tahun_energi),
        ("produksi_listrik", "Tenaga listrik yang dibangkitkan menurut provinsi",
         "CSV", "Belum dicantumkan", "", "GWh. Lengkapi sumber dan URL asal file ini.", FILE["produksi_listrik"], th_csv),
        ("kapasitas_pembangkit", "Kapasitas terpasang pembangkit listrik menurut provinsi",
         "XLSX", "Belum dicantumkan", "", "MW. Lengkapi sumber dan URL asal file ini.", FILE["kapasitas_pembangkit"], th_kap),
        ("sma_listrik", "Proporsi SMA yang memiliki akses listrik",
         "XLSX", "Pusdatin Kementerian Pendidikan Dasar dan Menengah", "", "Persen satuan pendidikan", FILE["sma_listrik"], th_sma),
        ("smk_listrik", "Proporsi SMK yang memiliki akses listrik",
         "XLSX", "Pusdatin Kementerian Pendidikan Dasar dan Menengah", "", "Persen satuan pendidikan", FILE["smk_listrik"], th_smk),
    ]
    db.execute("DELETE FROM sumber_data")
    db.executemany("INSERT INTO sumber_data (kode, nama, format_asal, sumber, url, keterangan, file_asal, tahun_data, data_contoh) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)", sumber)
    log(f"  {'sumber_data':<22} {len(sumber)} baris")
    log("Selesai.")


if __name__ == "__main__":
    main()
