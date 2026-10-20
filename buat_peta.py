"""
Ubah GeoJSON 38 provinsi menjadi jalur SVG ringan (static/peta.json).
Hanya perlu dijalankan ulang kalau file GeoJSON diganti.

Sumber peta: Indonesia GeoJSON & TopoJSON Maps (38 Provinces), Deny Herianto, CC BY 4.0
https://github.com/denyherianto/indonesia-geojson-topojson-maps-with-38-provinces
Perubahan: diproyeksikan ke bidang datar, koordinat dibulatkan, titik yang terlalu rapat dibuang.
"""
import json
import os

import db
from etl_lokal import normal

DIR = os.path.dirname(os.path.abspath(__file__))
LON0, LON1, LAT0, LAT1 = 94.6, 141.4, 6.3, -11.2
LEBAR = 1000
SKALA = LEBAR / (LON1 - LON0)
TINGGI = round((LAT0 - LAT1) * SKALA)


def titik(lon, lat):
    return (round((lon - LON0) * SKALA, 1), round((LAT0 - lat) * SKALA, 1))


def jalur(rings):
    d = []
    for ring in rings:
        pts, last = [], None
        for lon, lat in ring:
            p = titik(lon, lat)
            if last is None or abs(p[0] - last[0]) + abs(p[1] - last[1]) >= 0.6:
                pts.append(p)
                last = p
        if len(pts) < 3:
            continue
        d.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
    return "".join(d)


def main():
    g = json.load(open(os.path.join(DIR, "data", "peta", "indonesia-38-provinces.geojson"), encoding="utf-8"))
    kode = {normal(r["nama"]): r["kode_bps"] for r in db.query("SELECT kode_bps, nama FROM provinsi")}
    hasil = []
    for f in g["features"]:
        nama = f["properties"]["PROVINSI"]
        k = kode.get(normal(nama))
        if k is None:
            raise SystemExit(f"Provinsi peta tidak dikenali: {nama}")
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        d = "".join(jalur(p) for p in polys)
        hasil.append({"kode_bps": k, "d": d})
    out = {"lebar": LEBAR, "tinggi": TINGGI, "provinsi": sorted(hasil, key=lambda x: x["kode_bps"])}
    path = os.path.join(DIR, "static", "peta.json")
    json.dump(out, open(path, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"{len(hasil)} provinsi -> {path} ({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    main()
