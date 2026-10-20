// Fungsi bersama untuk semua halaman.
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Warna dipakai konsisten: biru tua = besaran (produksi/kapasitas), oranye panas = kekurangan akses.
const WARNA = {
  ink: css("--ink"),
  redup: "#C9C2B3",
  volt: css("--volt"),
  kurang: css("--hot"),
  sma: css("--ink"),
  smk: "#8D877B",
};

const nf = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 });
function ringkas(n) {
  if (n == null) return "–";
  if (Math.abs(n) >= 1e6) return nf.format(n / 1e6) + " juta";
  if (Math.abs(n) >= 1e3) return nf.format(n / 1e3) + " ribu";
  return nf.format(n);
}

async function api(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (res.status === 401) { window.location = "/masuk"; throw new Error("belum masuk"); }
  if (!res.ok) throw new Error(`Gagal memuat ${path} (${res.status})`);
  return res.json();
}

// Tulis keterangan sumber di bawah tiap blok, dari tabel sumber_data.
// data-src boleh berisi beberapa kode dipisah spasi.
function tulisSumber(sumber) {
  const peta = Object.fromEntries(sumber.map((s) => [s.kode, s]));
  document.querySelectorAll("[data-src]").forEach((el) => {
    const daftar = el.dataset.src.split(/\s+/).map((k) => peta[k]).filter(Boolean);
    el.innerHTML = "";
    if (!daftar.length) return;
    el.append("Sumber: ");
    daftar.forEach((s, i) => {
      if (i) el.append("; ");
      if (s.url) {
        const a = document.createElement("a");
        a.href = s.url; a.target = "_blank"; a.rel = "noopener"; a.textContent = s.sumber;
        el.append(a);
      } else {
        el.append(s.sumber);
      }
      if (s.tahun_data) el.append(`, ${s.tahun_data}`);
      const tag = document.createElement("span");
      tag.className = "fmt"; tag.textContent = s.format_asal; tag.title = "Format file asal";
      el.append(tag);
    });
  });
  const note = document.getElementById("dummy-note");
  if (note) note.hidden = !sumber.some((s) => Number(s.data_contoh));
}

// Gaya dasar Chart.js supaya semua grafik seragam
function gayaChart() {
  if (!window.Chart) return;
  Chart.defaults.font.family = "Montserrat, system-ui, sans-serif";
  Chart.defaults.font.size = 13;
  Chart.defaults.font.weight = 600;
  Chart.defaults.color = css("--ink");
  Chart.defaults.borderColor = css("--line-2");
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation.duration = 400;
  Chart.defaults.plugins.legend.position = "bottom";
  Chart.defaults.plugins.legend.align = "start";
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.legend.labels.boxHeight = 12;
  Chart.defaults.plugins.legend.labels.padding = 14;
  Chart.defaults.plugins.tooltip.backgroundColor = css("--ink");
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 0;
  Chart.defaults.plugins.tooltip.titleColor = css("--volt");
  Chart.defaults.plugins.tooltip.boxPadding = 4;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) Chart.defaults.animation = false;
}
