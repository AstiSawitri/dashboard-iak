"""Bikin logo ARUS (SVG + PNG) ke static/img/.

    python tools/buat_logo.py

Ikon: kotak kuning rambu dengan petir hitam yang menembus keluar kotak (arus listrik yang "tumpah").
Wordmark: huruf ARUS diambil dari kerangka huruf Inter Display Black lalu disimpan sebagai path,
jadi logonya tidak bergantung pada font yang terpasang. PNG dirender dengan Chromium (Playwright).
Perlu: fonttools, playwright, dan font Inter Display Black (hanya untuk membuat ulang logo).
"""
import asyncio
import os

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "img")
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"

KUNING, TINTA, KERTAS = "#FFD60A", "#121212", "#EDE8DD"

# ikon 120 x 120: kotak 92 x 92, petir keluar dari atas dan bawah kotak
KOTAK = '<rect x="12" y="16" width="92" height="92" fill="{k}"/>'
PETIR = '<polygon points="66,0 28,68 56,68 42,120 100,46 72,46 90,0" fill="{t}"{garis}/>'
# di latar gelap petir diberi garis tepi warna kertas supaya ujungnya tetap terlihat
GARIS_GELAP = ' stroke="#EDE8DD" stroke-width="3" stroke-linejoin="miter" paint-order="stroke"'


def ikon_svg(kotak=KUNING, petir=TINTA, latar=None, ukuran=120):
    bg = f'<rect width="120" height="120" fill="{latar}"/>' if latar else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="{ukuran}" height="{ukuran}">'
            f'{bg}{KOTAK.format(k=kotak)}{PETIR.format(t=petir, garis="")}</svg>')


def wordmark_paths(teks="ARUS", tracking=0.0):
    f = TTFont(FONT)
    gs, cmap = f.getGlyphSet(), f.getBestCmap()
    upm = f["head"].unitsPerEm
    cap = f["OS/2"].sCapHeight
    x, paths = 0, []
    for ch in teks:
        g = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        gs[g].draw(pen)
        paths.append((x, pen.getCommands()))
        x += gs[g].width + tracking * upm
    lebar = x - tracking * upm
    return paths, lebar, cap


def logo_svg(warna_teks=TINTA, tinggi=120, gelap=False):
    """Lockup horizontal: ikon + ARUS. Tinggi huruf kapital = tinggi kotak kuning (92/120)."""
    paths, lebar, cap = wordmark_paths()
    skala = 92 / cap
    gx = 128                                   # jarak ikon ke huruf
    lebar_total = gx + lebar * skala
    g = "".join(f'<path transform="translate({gx + x * skala:.2f},108) scale({skala:.5f},{-skala:.5f})" d="{d}"/>'
                for x, d in paths)
    m = 3                                      # ruang untuk garis tepi petir
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-m} {-m} {lebar_total + 2 * m:.1f} {120 + 2 * m}" '
            f'height="{tinggi}" width="{(lebar_total + 2 * m) * tinggi / (120 + 2 * m):.0f}">'
            f'{KOTAK.format(k=KUNING)}{PETIR.format(t=TINTA, garis=GARIS_GELAP if gelap else "")}<g fill="{warna_teks}">{g}</g></svg>')


async def render(svg, path, lebar=None, tinggi=None):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(device_scale_factor=1)
        await pg.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
        el = await pg.query_selector("svg")
        await el.screenshot(path=path, omit_background=True)
        await b.close()


def main():
    os.makedirs(OUT, exist_ok=True)
    berkas = {
        "arus-logo.svg": logo_svg(TINTA),
        "arus-logo-terang.svg": logo_svg(KERTAS, gelap=True),
        "arus-ikon.svg": ikon_svg(),
    }
    for nama, svg in berkas.items():
        open(os.path.join(OUT, nama), "w", encoding="utf-8").write(svg)
    png = [
        (logo_svg(TINTA, 360), "arus-logo.png"),            # untuk latar terang
        (logo_svg(KERTAS, 360, gelap=True), "arus-logo-terang.png"),    # untuk latar gelap
        (ikon_svg(ukuran=512), "arus-ikon.png"),
        (ikon_svg(ukuran=180, latar=KERTAS), "apple-touch-icon.png"),
        (ikon_svg(ukuran=32, latar=KERTAS), "favicon-32.png"),
    ]
    for svg, nama in png:
        asyncio.run(render(svg, os.path.join(OUT, nama)))
        print("dibuat", nama)


if __name__ == "__main__":
    main()
