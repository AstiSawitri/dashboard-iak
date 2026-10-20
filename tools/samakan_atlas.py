"""Ubah CSS ARUS supaya tampilannya menyatu dengan web utama.

1. Semua aturan dibatasi ke wrapper `.arus` (tidak bocor ke topbar/halaman lain).
2. Aturan halaman login/landing ARUS dan tema gelap dibuang (login memakai web utama).
3. Semua warna diganti ke palet web utama (tinta biru tua, kertas, kuning volt, merah bata).
4. Font, sudut, dan bayangan disamakan.

Jalankan dari folder proyek:  python tools/samakan_atlas.py data/arus_styles_asli.css static/atlas/styles.css
"""
import colorsys
import re
import sys

WRAP = ".arus"

# Palet web utama, per keluarga warna, dari gelap ke terang.
INK = ["#182640", "#22345A", "#3F577C", "#4D5A70", "#6F87A5", "#7E899B", "#A7B6C9", "#D6DCE0", "#E6EAEC", "#F2F4F3"]
BATA = ["#8E2F17", "#A83A1F", "#C2502E", "#E59A6C", "#F3D6C2", "#FBE9E4"]
VOLT = ["#7A5E00", "#E3A80B", "#F2C014", "#FBEFB8", "#FDF7DC"]
HIJAU = ["#2D6B4A", "#5E8C3A", "#CFE3D6", "#EAF3EC"]
NETRAL = ["#182640", "#4D5A70", "#7E899B", "#B9C3CF", "#D6DCE0", "#E6EAEC", "#F2F4F3", "#FAFBFB", "#FFFFFF"]


def _rgb(h):
    h = h.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], (h[6:8] if len(h) == 8 else "")


def _lum(rgb):
    return colorsys.rgb_to_hls(*rgb)[1]


def _terdekat(rgb, ramp):
    l = _lum(rgb)
    return min(ramp, key=lambda c: abs(_lum(_rgb(c)[0]) - l))


def petakan(rgb):
    h, l, s = colorsys.rgb_to_hls(*rgb)
    deg = h * 360
    if l > 0.985:
        return "#FFFFFF"
    if s < 0.18 or l < 0.12 or (l > 0.93 and s < 0.6):
        return _terdekat(rgb, NETRAL)
    if deg < 40 or deg >= 330:
        return _terdekat(rgb, BATA)
    if deg < 75:
        return _terdekat(rgb, VOLT)
    if deg < 100 and l > 0.6:          # hijau limau ARUS = aksen, jadi kuning volt
        return _terdekat(rgb, VOLT)
    if deg < 160 and l > 0.25 and s > 0.3 and l < 0.55:
        return _terdekat(rgb, HIJAU)   # hijau "baik"
    return _terdekat(rgb, INK)         # teal, biru, ungu ARUS -> tinta


def ganti_warna(css):
    def hex_(m):
        rgb, a = _rgb(m.group(0))
        return petakan(rgb) + a.upper()

    def rgba_(m):
        r, g, b, a = [x.strip() for x in m.group(1).split(",")]
        baru, _ = _rgb(petakan([int(r) / 255, int(g) / 255, int(b) / 255]))
        return "rgba(%d,%d,%d,%s)" % (round(baru[0] * 255), round(baru[1] * 255), round(baru[2] * 255), a)

    css = re.sub(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3,4}\b", hex_, css)
    css = re.sub(r"rgba\(([^)]*)\)", rgba_, css)
    return css


def rapikan_ukuran(css):
    """Huruf ARUS kecil (9-13px); web utama 14-16px. Sudut dan bayangan disamakan (4px, tanpa bayangan)."""
    def fs(m):
        px = float(m.group(1))
        baru = px * 0.6 + 7.5 if px <= 20 else px
        return "font-size:%gpx" % round(baru, 1)
    css = re.sub(r"font-size:(\d+(?:\.\d+)?)px", fs, css)

    def rad(m):
        px = float(m.group(1))
        return "border-radius:4px" if 3 <= px <= 30 else m.group(0)
    css = re.sub(r"border-radius:(\d+(?:\.\d+)?)px(?=[;}])", rad, css)
    css = re.sub(r"box-shadow:[^;}]*", "box-shadow:none", css)
    css = re.sub(r"backdrop-filter:[^;}]*;?", "", css)
    css = re.sub(r"transform:translateY\(-?\d+px\)", "transform:none", css)
    css = re.sub(r"letter-spacing:-[\d.]+px", "letter-spacing:-0.01em", css)
    return css


def pecah(css):
    """Pecah CSS jadi daftar (prelude, isi) di level teratas."""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find("{", i)
        k = css.find(";", i)
        if j == -1:
            break
        if k != -1 and k < j:              # @charset, @import
            out.append((css[i:k].strip(), None))
            i = k + 1
            continue
        depth, p = 1, j + 1
        while depth:
            c = css[p]
            depth += c == "{"
            depth -= c == "}"
            p += 1
        out.append((css[i:j].strip(), css[j + 1:p - 1]))
        i = p
    return out


BUANG = re.compile(r"\.dark|landing|login|\.boot\b|#boot|\.sidebar|\.scrim|\.main-shell|\.breadcrumb|\.top-actions|"
                   r"\.date-chip|\.avatar|\.logout-button|\.top-divider|\.mobile-menu|\.footer|\.workspace-label|"
                   r"\.nav-item|\.nav-dot|\.live-dot|\.note-bolt|\.side-link")


def lingkup(sel):
    hasil = []
    for s in sel.split(","):
        s = s.strip()
        if not s:
            continue
        if BUANG.search(s):
            continue
        s2 = re.sub(r"^(:root|html|body)(?=$|[\s.:>\[#])", WRAP, s)
        if s2 == s:
            s2 = WRAP + " " + s
        hasil.append(s2)
    return ",".join(hasil)


def proses(css):
    out = []
    for pre, isi in pecah(css):
        if isi is None:
            continue                                   # @charset dibuang (file sudah UTF-8)
        if pre.startswith("@keyframes"):
            out.append(pre + "{" + isi + "}")
        elif pre.startswith("@media") or pre.startswith("@supports"):
            dalam = proses(isi)
            if dalam.strip():
                out.append(pre + "{" + dalam + "}")
        elif pre.startswith("@"):
            out.append(pre + "{" + isi + "}")
        else:
            sel = lingkup(pre)
            if sel:
                out.append(sel + "{" + isi + "}")
    return "\n".join(out)


def main(src, dst):
    css = open(src, encoding="utf-8").read()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = css.replace('"Segoe UI",Arial,sans-serif', '"Montserrat",system-ui,sans-serif')
    css = proses(css)
    css = ganti_warna(css)
    css = rapikan_ukuran(css)
    kepala = "/* CSS dashboard ARUS (anggota kelompok), dibatasi ke .arus dan diberi palet web utama oleh tools/samakan_atlas.py. */\n"
    open(dst, "w", encoding="utf-8").write(kepala + css + "\n")
    print("selesai:", dst, len(css), "byte")


if __name__ == "__main__":
    main(*sys.argv[1:3])
