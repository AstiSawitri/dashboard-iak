// Dasbor ringkasan: ambil data gabungan dari API lalu gambar peta, angka utama, dan grafik.
gayaChart();

const state = { wilayah: "", kode: null, indikator: "rumah_tangga_persen" };
let PROV = [];        // satu baris per provinsi, hasil /api/gabungan (kelima dataset sudah digabung)
let NAS = null;       // baris nasional (kode 99)
let SUMBER = [];
const charts = {};
const $ = (id) => document.getElementById(id);
const persen = (v, d = 2) => (v == null ? "–" : new Intl.NumberFormat("id-ID", { maximumFractionDigits: d }).format(v));

const INDIKATOR = {
  rumah_tangga_persen: { judul: "Rumah tangga berlistrik", jenis: "akses", satuan: "%" },
  rumah_tangga_desa_persen: { judul: "Rumah tangga perdesaan berlistrik", jenis: "akses", satuan: "%" },
  produksi_gwh: { judul: "Listrik dibangkitkan", jenis: "besaran", satuan: "GWh" },
  kapasitas_mw: { judul: "Kapasitas terpasang", jenis: "besaran", satuan: "MW" },
};

// ---------------------------------------------------------------- data turunan
const dalamLingkup = (p) => !state.wilayah || p.wilayah === state.wilayah;
const lingkup = () => PROV.filter(dalamLingkup);
const terpilih = () => PROV.find((p) => p.kode_bps === state.kode) || null;
const jumlah = (rows, k) => rows.reduce((s, r) => s + (r[k] || 0), 0);
const urutTurun = (rows, k) => [...rows].filter((r) => r[k] != null).sort((a, b) => b[k] - a[k]);
const peringkat = (p, k) => 1 + PROV.filter((r) => r[k] != null && r[k] > p[k]).length;

// ---------------------------------------------------------------- awal
async function mulai() {
  const [meta, gab, peta] = await Promise.all([
    api("/api/meta"),
    api("/api/gabungan?nasional=1"),
    fetch("/static/peta.json").then((r) => r.json()),
  ]);
  SUMBER = meta.sumber;
  tulisSumber(SUMBER);
  NAS = gab.data.find((r) => r.kode_bps === 99) || null;
  PROV = gab.data.filter((r) => r.kode_bps !== 99);

  const w = $("wilayah");
  meta.wilayah.forEach((x) => w.add(new Option(x, x)));
  w.addEventListener("change", () => { state.wilayah = w.value; if (terpilih() && !dalamLingkup(terpilih())) state.kode = null; perbarui(); });
  $("provinsi").addEventListener("change", (e) => { state.kode = e.target.value ? Number(e.target.value) : null; perbarui(); });
  $("reset").addEventListener("click", () => { state.wilayah = ""; state.kode = null; w.value = ""; perbarui(); });

  document.querySelectorAll("#indikator button").forEach((b) =>
    b.addEventListener("click", () => { state.indikator = b.dataset.k; gambarPeta(); }));

  siapkanPeta(peta);
  perbarui();
}

function pilih(kode) {
  state.kode = state.kode === kode ? null : kode;
  perbarui();
}

async function perbarui() {
  // daftar provinsi mengikuti wilayah
  const sel = $("provinsi");
  sel.length = 1;
  lingkup().forEach((p) => sel.add(new Option(p.provinsi, p.kode_bps)));
  sel.value = state.kode || "";
  $("wilayah").value = state.wilayah;
  $("reset").hidden = !state.wilayah && !state.kode;

  const q = state.kode ? `?kode=${state.kode}` : "";
  const ring = await api(`/api/ringkasan${q}`);   // angka utama dihitung di server (lapisan logika)
  gambarAngka(ring);
  gambarJudul();
  gambarPeta();
  gambarProduksi();
  gambarKapasitas();
  gambarRumahTangga();
  gambarSekolah();
}

// ---------------------------------------------------------------- judul + angka utama
function gambarJudul() {
  const p = terpilih();
  const rows = lingkup();
  const urutRT = [...rows].sort((a, b) => a.rumah_tangga_persen - b.rumah_tangga_persen);
  const fokus = p || urutRT[0];
  const tinggi = urutRT[urutRT.length - 1];

  // angka raksasa
  const num = $("hero-num");
  num.textContent = persen(fokus.rumah_tangga_persen);
  const kecil = document.createElement("small"); kecil.textContent = "%";
  num.append(kecil);
  num.classList.toggle("panas", fokus.rumah_tangga_persen < 95);

  // kalimat di bawahnya, nama provinsi distabilo
  const line = $("hero-line");
  line.textContent = "";
  const mark = document.createElement("mark"); mark.textContent = fokus.provinsi;
  line.append("rumah tangga di ", mark, " punya listrik.");

  const vs = $("hero-vs");
  vs.textContent = "";
  const b = (t) => { const el = document.createElement("b"); el.textContent = t; return el; };
  if (p) {
    vs.append("Peringkat ", b(`${peringkat(p, "rumah_tangga_persen")} dari ${PROV.length}`), " provinsi. Nasional ", b(`${persen(NAS.rumah_tangga_persen)}%`), ".");
  } else if (state.wilayah) {
    vs.append(`Terendah di ${state.wilayah}. Tertinggi: `, b(`${tinggi.provinsi} ${persen(tinggi.rumah_tangga_persen)}%`), ".");
  } else {
    vs.append("Terendah di Indonesia. Nasional ", b(`${persen(NAS.rumah_tangga_persen)}%`), ", tertinggi ", b(`${tinggi.provinsi} ${persen(tinggi.rumah_tangga_persen)}%`), ".");
  }

  // pita kuning: siapa yang membangkitkan listrik
  let band, note;
  if (p) {
    band = `${p.provinsi} membangkitkan ${persen(p.produksi_gwh / NAS.produksi_gwh * 100, 1)}% listrik nasional.`;
    note = `${nf0.format(p.produksi_gwh)} GWh pada 2024, peringkat ${peringkat(p, "produksi_gwh")} dari ${PROV.length} provinsi.`;
  } else if (state.wilayah) {
    const top = urutTurun(rows, "produksi_gwh")[0], tot = jumlah(rows, "produksi_gwh");
    band = `${top.provinsi} membangkitkan ${persen(top.produksi_gwh / tot * 100, 1)}% listrik ${state.wilayah}.`;
    note = `${nf0.format(top.produksi_gwh)} dari ${nf0.format(tot)} GWh di ${rows.length} provinsi, 2024.`;
  } else {
    const jawa = PROV.filter((r) => r.wilayah === "Jawa"), gwh = jumlah(jawa, "produksi_gwh");
    band = `Jawa membangkitkan ${persen(gwh / NAS.produksi_gwh * 100, 1)}% listrik Indonesia.`;
    note = `Enam provinsi, ${nf0.format(gwh)} dari ${nf0.format(NAS.produksi_gwh)} GWh pada 2024. Sisanya dibagi 32 provinsi.`;
  }
  $("band").textContent = band;
  $("band-note").textContent = note;
}

function gambarAngka(ring) {
  const p = terpilih();
  const rows = lingkup();
  const N = PROV.length;
  const set = (id, v) => ($(id).textContent = v);

  if (p) {
    const rk = ring.peringkat || {};
    set("k-produksi", nf0.format(p.produksi_gwh));
    set("k-produksi-d", `${persen(p.produksi_gwh / NAS.produksi_gwh * 100, 1)}% dari total nasional, peringkat ${rk.produksi_gwh} dari ${N}`);
    set("k-kapasitas", nf0.format(p.kapasitas_mw));
    set("k-kapasitas-d", `Peringkat ${rk.kapasitas_mw} dari ${N}. Perkiraan faktor kapasitas ${persen(p.faktor_kapasitas_persen, 1)}%`);
    set("k-rt", persen(p.rumah_tangga_persen));
    set("k-rt-d", `Kota ${persen(p.rumah_tangga_kota_persen)}%, desa ${p.rumah_tangga_desa_persen == null ? "tidak tersedia" : persen(p.rumah_tangga_desa_persen) + "%"}`);
    set("k-sekolah", `${persen(p.sma_persen, 1)} / ${persen(p.smk_persen, 1)}`);
    set("k-sekolah-d", "Data sekolah tahun 2023");
    $("scope").textContent = `Angka untuk ${p.provinsi}. Produksi, kapasitas, dan rumah tangga: data 2024.`;
  } else if (state.wilayah) {
    const gwh = jumlah(rows, "produksi_gwh"), mw = jumlah(rows, "kapasitas_mw");
    const rendahRT = [...rows].sort((a, b) => a.rumah_tangga_persen - b.rumah_tangga_persen)[0];
    const rendahSek = [...rows].sort((a, b) => Math.min(a.sma_persen, a.smk_persen) - Math.min(b.sma_persen, b.smk_persen))[0];
    set("k-produksi", nf0.format(gwh));
    set("k-produksi-d", `${persen(gwh / NAS.produksi_gwh * 100, 1)}% dari total nasional, ${rows.length} provinsi`);
    set("k-kapasitas", nf0.format(mw));
    set("k-kapasitas-d", `${persen(mw / NAS.kapasitas_mw * 100, 1)}% dari total nasional`);
    set("k-rt", persen(rendahRT.rumah_tangga_persen));
    set("k-rt-d", `Terendah di wilayah ini: ${rendahRT.provinsi}`);
    set("k-sekolah", `${persen(rendahSek.sma_persen, 1)} / ${persen(rendahSek.smk_persen, 1)}`);
    set("k-sekolah-d", `Terendah di wilayah ini: ${rendahSek.provinsi}`);
    $("scope").textContent = `Produksi dan kapasitas dijumlahkan untuk ${state.wilayah}. Persentase tidak dirata-rata karena tidak ada data jumlah rumah tangga atau sekolah sebagai bobot, jadi yang ditampilkan adalah provinsi terendah.`;
  } else {
    const n = ring.nilai;
    const jawa = PROV.filter((r) => r.wilayah === "Jawa");
    set("k-produksi", nf0.format(n.produksi_gwh));
    set("k-produksi-d", `Pulau Jawa menyumbang ${persen(jumlah(jawa, "produksi_gwh") / n.produksi_gwh * 100, 1)}%`);
    set("k-kapasitas", nf0.format(n.kapasitas_mw));
    set("k-kapasitas-d", `Perkiraan faktor kapasitas nasional ${persen(n.faktor_kapasitas_persen, 1)}%`);
    set("k-rt", persen(n.rumah_tangga_persen));
    set("k-rt-d", `Kota ${persen(n.rumah_tangga_kota_persen)}%, desa ${persen(n.rumah_tangga_desa_persen)}%`);
    set("k-sekolah", `${persen(n.sma_persen, 1)} / ${persen(n.smk_persen, 1)}`);
    set("k-sekolah-d", "Data sekolah tahun 2023");
    $("scope").textContent = "Angka nasional dari baris INDONESIA di tiap sumber. Produksi, kapasitas, dan rumah tangga: data 2024. Sekolah: data 2023.";
  }
}

// ---------------------------------------------------------------- peta
const AKSES_BATAS = [70, 90, 98, 99.5];
const AKSES_WARNA = ["#FF4B1F", "#FF8A3D", "#FFD60A", "#8A8477", "#3D3B36"];   // di atas latar hitam
const BESAR_WARNA = ["#3D3B36", "#5C5126", "#9C8418", "#D8B20C", "#FFD60A"];
let skala = null;

function buatSkala(k) {
  const info = INDIKATOR[k];
  if (info.jenis === "akses") {
    const label = ["di bawah 70%", "70 sampai 90%", "90 sampai 98%", "98 sampai 99,5%", "99,5% ke atas"];
    return {
      warna: (v) => (v == null ? null : AKSES_WARNA[AKSES_BATAS.filter((b) => v >= b).length]),
      legenda: AKSES_WARNA.map((c, i) => ({ c, t: label[i] })),
    };
  }
  // besaran: 5 kelas berdasarkan kuantil supaya provinsi kecil tetap terlihat bedanya
  const v = PROV.map((p) => p[k]).filter((x) => x != null).sort((a, b) => a - b);
  const q = [0.2, 0.4, 0.6, 0.8].map((f) => v[Math.floor(f * (v.length - 1))]);
  const batas = [v[0], ...q, v[v.length - 1]];
  return {
    warna: (x) => (x == null ? null : BESAR_WARNA[q.filter((b) => x > b).length]),
    legenda: BESAR_WARNA.map((c, i) => ({ c, t: `${ringkas(batas[i])} sampai ${ringkas(batas[i + 1])} ${info.satuan}` })),
  };
}

function siapkanPeta(peta) {
  const svg = $("peta");
  svg.setAttribute("viewBox", `0 0 ${peta.lebar} ${peta.tinggi}`);
  const NS = "http://www.w3.org/2000/svg";
  peta.provinsi.forEach((f) => {
    const p = PROV.find((r) => r.kode_bps === f.kode_bps);
    if (!p) return;
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", f.d);
    path.dataset.kode = f.kode_bps;
    path.setAttribute("tabindex", "0");
    path.setAttribute("role", "button");
    path.setAttribute("aria-label", p.provinsi);
    path.addEventListener("click", () => pilih(f.kode_bps));
    path.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pilih(f.kode_bps); } });
    path.addEventListener("mousemove", (e) => tampilTip(e, p));
    path.addEventListener("mouseleave", () => ($("tip").hidden = true));
    path.addEventListener("focus", () => path.parentNode.appendChild(path));
    svg.append(path);
  });
}

function tampilTip(e, p) {
  const k = state.indikator, info = INDIKATOR[k];
  const tip = $("tip");
  const v = p[k];
  tip.innerHTML = "";
  const b = document.createElement("b"); b.textContent = p.provinsi;
  tip.append(b, document.createElement("br"),
    `${info.judul}: ${v == null ? "tidak tersedia" : (info.jenis === "akses" ? persen(v) : nf0.format(v)) + " " + info.satuan}`);
  const box = $("peta").getBoundingClientRect();
  tip.style.left = `${Math.min(e.clientX - box.left + 14, box.width - 220)}px`;
  tip.style.top = `${e.clientY - box.top + 14}px`;
  tip.hidden = false;
}

function gambarPeta() {
  const k = state.indikator;
  skala = buatSkala(k);
  document.querySelectorAll("#indikator button").forEach((b) => b.setAttribute("aria-checked", b.dataset.k === k));
  document.querySelectorAll("#peta path").forEach((el) => {
    const p = PROV.find((r) => r.kode_bps === Number(el.dataset.kode));
    const c = skala.warna(p[k]);
    el.style.fill = c || "#555";
    el.classList.toggle("luar", !dalamLingkup(p));
    el.classList.toggle("aktif", p.kode_bps === state.kode);
    if (p.kode_bps === state.kode) el.parentNode.appendChild(el);
  });
  const lg = $("legend");
  lg.innerHTML = "";
  skala.legenda.forEach((x) => {
    const li = document.createElement("li");
    const sw = document.createElement("i"); sw.className = "sw"; sw.style.setProperty("--c", x.c);
    li.append(sw, x.t);
    lg.append(li);
  });
  if (PROV.some((p) => p[k] == null)) {
    const li = document.createElement("li");
    const sw = document.createElement("i"); sw.className = "sw"; sw.style.setProperty("--c", "#555");
    li.append(sw, "tidak tersedia");
    lg.append(li);
  }
}

// ---------------------------------------------------------------- grafik
function buat(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($(id), config);
}

function tinggiBaris(id, n) {
  $(id).parentElement.style.height = `${Math.max(240, n * 21 + 80)}px`;
}

function klikProvinsi(labelsKode) {
  return (_, el) => { if (el.length) pilih(labelsKode[el[0].index]); };
}

function warnaBatang(p) {
  if (!state.kode) return WARNA.ink;
  return p.kode_bps === state.kode ? WARNA.kurang : WARNA.redup;
}

function gambarProduksi() {
  const rows = urutTurun(lingkup(), "produksi_gwh");
  tinggiBaris("c-produksi", rows.length);
  buat("c-produksi", {
    type: "bar",
    data: {
      labels: rows.map((r) => r.provinsi),
      datasets: [{
        data: rows.map((r) => r.produksi_gwh),
        backgroundColor: rows.map(warnaBatang),
        borderColor: rows.map((r) => (r.kode_bps === state.kode ? WARNA.ink : "transparent")),
        borderWidth: 1.5, barPercentage: 0.75,
      }],
    },
    options: {
      indexAxis: "y",
      scales: {
        x: { ticks: { callback: (v) => ringkas(v) }, title: { display: true, text: "GWh" } },
        y: { grid: { display: false }, ticks: { autoSkip: false, color: WARNA.ink } },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => ` ${nf.format(c.raw)} GWh (${persen(c.raw / NAS.produksi_gwh * 100, 1)}% nasional)` } },
      },
      onClick: klikProvinsi(rows.map((r) => r.kode_bps)),
    },
  });

  const p = terpilih();
  let teks;
  if (p) {
    teks = `${p.provinsi} membangkitkan ${nf.format(p.produksi_gwh)} GWh, atau ${persen(p.produksi_gwh / NAS.produksi_gwh * 100, 1)}% listrik nasional.`;
  } else if (state.wilayah) {
    const tot = jumlah(rows, "produksi_gwh");
    teks = `${rows[0].provinsi} menyumbang ${persen(rows[0].produksi_gwh / tot * 100, 1)}% produksi listrik ${state.wilayah}.`;
  } else {
    const kecil = rows[rows.length - 1];
    teks = `${rows[0].provinsi} ${nf0.format(rows[0].produksi_gwh)} GWh. ${kecil.provinsi} cuma ${nf.format(kecil.produksi_gwh)} GWh.`;
  }
  $("note-produksi").textContent = teks;
}

function gambarKapasitas() {
  const all = PROV.filter((r) => r.produksi_gwh && r.kapasitas_mw);
  const xs = all.map((r) => r.kapasitas_mw);
  const xmin = Math.min(...xs) * 0.7, xmax = Math.max(...xs) * 1.4;
  const garis = (fk) => [{ x: xmin, y: xmin * 8.76 * fk }, { x: xmax, y: xmax * 8.76 * fk }];
  const warnaTitik = (r) => (r.kode_bps === state.kode ? WARNA.kurang : dalamLingkup(r) ? WARNA.ink : WARNA.redup);
  buat("c-kapasitas", {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Provinsi",
          data: all.map((r) => ({ x: r.kapasitas_mw, y: r.produksi_gwh, r })),
          backgroundColor: all.map(warnaTitik),
          borderColor: all.map((r) => (r.kode_bps === state.kode ? WARNA.ink : "transparent")),
          borderWidth: 1.5,
          pointRadius: all.map((r) => (r.kode_bps === state.kode ? 8 : dalamLingkup(r) ? 5 : 3.5)),
          pointHoverRadius: 8,
        },
        { label: "Faktor kapasitas 30%", type: "line", data: garis(0.3), borderColor: "#8D877B", borderDash: [4, 4], borderWidth: 1, pointRadius: 0 },
        { label: "Faktor kapasitas 70%", type: "line", data: garis(0.7), borderColor: "#8D877B", borderDash: [1, 3], borderWidth: 1.5, pointRadius: 0 },
      ],
    },
    options: {
      scales: {
        x: { type: "logarithmic", min: xmin, max: xmax, title: { display: true, text: "Kapasitas terpasang (MW)" },
             ticks: { callback: (v) => ([1, 10, 100, 1000, 10000].includes(v) ? nf0.format(v) : "") } },
        y: { type: "logarithmic", title: { display: true, text: "Listrik dibangkitkan (GWh)" },
             ticks: { callback: (v) => ([1, 10, 100, 1000, 10000, 100000].includes(v) ? nf0.format(v) : "") } },
      },
      plugins: {
        legend: { labels: { filter: (item) => item.datasetIndex > 0 } },
        tooltip: {
          filter: (c) => c.datasetIndex === 0,
          callbacks: {
            title: (items) => items[0].raw.r.provinsi,
            label: (c) => {
              const r = c.raw.r;
              return [` ${nf.format(r.kapasitas_mw)} MW`, ` ${nf.format(r.produksi_gwh)} GWh`, ` Faktor kapasitas ~${persen(r.faktor_kapasitas_persen, 1)}%`];
            },
          },
        },
      },
      onClick: (_, el) => { const t = el.find((e) => e.datasetIndex === 0); if (t) pilih(all[t.index].kode_bps); },
    },
  });

  const rows = urutTurun(lingkup(), "faktor_kapasitas_persen");
  const p = terpilih();
  const catatan = "";
  if (p) {
    $("note-kapasitas").textContent = `Pembangkit ${p.provinsi} terpakai sekitar ${persen(p.faktor_kapasitas_persen, 1)}% setahun. Nasional ${persen(NAS.faktor_kapasitas_persen, 1)}%.` + catatan;
  } else {
    const hi = rows[0], lo = rows[rows.length - 1];
    $("note-kapasitas").textContent = `Paling terpakai: ${hi.provinsi}, ~${persen(hi.faktor_kapasitas_persen, 0)}%. Paling longgar: ${lo.provinsi}, ${persen(lo.faktor_kapasitas_persen, 0)}%.` + catatan;
  }
}

function gambarRumahTangga() {
  const rows = [...lingkup()].sort((a, b) => a.rumah_tangga_persen - b.rumah_tangga_persen);
  tinggiBaris("c-rt", rows.length);
  const minX = Math.max(0, Math.floor(Math.min(...rows.map((r) => r.rumah_tangga_desa_persen ?? r.rumah_tangga_persen)) / 5) * 5 - 5);
  const sorot = (r) => !state.kode || r.kode_bps === state.kode;
  buat("c-rt", {
    type: "bar",
    data: {
      labels: rows.map((r) => r.provinsi),
      datasets: [
        {
          label: "Rentang desa sampai kota",
          data: rows.map((r) => (r.rumah_tangga_desa_persen == null ? null : [r.rumah_tangga_desa_persen, r.rumah_tangga_kota_persen])),
          backgroundColor: rows.map((r) => (sorot(r) ? WARNA.kurang : "#F2B7A6")),
          barPercentage: 0.28, borderSkipped: false, borderRadius: 0,
        },
        {
          label: "Total provinsi",
          type: "line", showLine: false,
          data: rows.map((r) => r.rumah_tangga_persen),
          pointBackgroundColor: rows.map((r) => (r.kode_bps === state.kode ? WARNA.volt : sorot(r) ? WARNA.ink : WARNA.redup)),
          pointBorderColor: WARNA.ink, pointBorderWidth: rows.map((r) => (r.kode_bps === state.kode ? 1.5 : 0)),
          pointRadius: rows.map((r) => (r.kode_bps === state.kode ? 7 : 4.5)),
        },
      ],
    },
    options: {
      indexAxis: "y",
      scales: {
        x: { min: minX, max: 100, title: { display: true, text: "Persen rumah tangga" } },
        y: { grid: { display: false }, ticks: { autoSkip: false, color: WARNA.ink } },
      },
      plugins: {
        tooltip: {
          mode: "index", intersect: false,
          callbacks: {
            label: (c) => {
              const r = rows[c.dataIndex];
              if (c.datasetIndex === 0) return r.rumah_tangga_desa_persen == null ? " Desa: tidak tersedia" : [` Desa: ${persen(r.rumah_tangga_desa_persen)}%`, ` Kota: ${persen(r.rumah_tangga_kota_persen)}%`];
              return ` Total: ${persen(r.rumah_tangga_persen)}%`;
            },
          },
        },
      },
      onClick: klikProvinsi(rows.map((r) => r.kode_bps)),
    },
  });

  const p = terpilih();
  let teks;
  if (p) {
    teks = p.rumah_tangga_desa_persen == null
      ? `${p.provinsi} tidak punya angka perdesaan di sumber data; angka perkotaan dan totalnya ${persen(p.rumah_tangga_persen)}%.`
      : `Di ${p.provinsi}, ${persen(p.rumah_tangga_kota_persen)}% rumah tangga kota dan ${persen(p.rumah_tangga_desa_persen)}% rumah tangga desa sudah berlistrik, selisih ${persen(p.selisih_kota_desa_poin)} poin.`;
  } else {
    const lebar = urutTurun(rows, "selisih_kota_desa_poin")[0];
    teks = `${lebar.provinsi}: kota ${persen(lebar.rumah_tangga_kota_persen, 0)}%, desa ${persen(lebar.rumah_tangga_desa_persen, 0)}%.`;
  }
  $("note-rt").textContent = teks;
}

function gambarSekolah() {
  const scope = lingkup();
  const kurang = scope.filter((r) => r.sma_persen < 100 || r.smk_persen < 100)
    .sort((a, b) => Math.min(a.sma_persen, a.smk_persen) - Math.min(b.sma_persen, b.smk_persen));
  const penuh = scope.length - kurang.length;
  const kosong = !kurang.length;
  $("c-sekolah").hidden = kosong;
  $("sekolah-empty").hidden = !kosong;
  $("sekolah-empty").textContent = kosong ? `Semua SMA dan SMK di ${state.wilayah || "Indonesia"} sudah memiliki akses listrik.` : "";
  if (charts["c-sekolah"]) { charts["c-sekolah"].destroy(); delete charts["c-sekolah"]; }
  if (!kosong) {
    tinggiBaris("c-sekolah", kurang.length * 1.2);
    const redup = (c, r) => (!state.kode || r.kode_bps === state.kode ? c : c + "55");
    buat("c-sekolah", {
      type: "bar",
      data: {
        labels: kurang.map((r) => r.provinsi),
        datasets: [
          { label: "SMA", data: kurang.map((r) => r.sma_persen), backgroundColor: kurang.map((r) => redup(WARNA.sma, r)), barPercentage: 0.8, categoryPercentage: 0.75 },
          { label: "SMK", data: kurang.map((r) => r.smk_persen), backgroundColor: kurang.map((r) => redup(WARNA.smk, r)), barPercentage: 0.8, categoryPercentage: 0.75 },
        ],
      },
      options: {
        indexAxis: "y",
        scales: {
          x: { min: Math.floor(Math.min(...kurang.map((r) => Math.min(r.sma_persen, r.smk_persen))) / 5) * 5 - 5, max: 100, title: { display: true, text: "Persen sekolah berlistrik" } },
          y: { grid: { display: false }, ticks: { autoSkip: false, color: WARNA.ink } },
        },
        plugins: { tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${persen(c.raw)}%` } } },
        onClick: klikProvinsi(kurang.map((r) => r.kode_bps)),
      },
    });
  }

  const p = terpilih();
  let teks;
  if (p) {
    teks = p.sma_persen >= 100 && p.smk_persen >= 100
      ? `Semua SMA dan SMK di ${p.provinsi} sudah berlistrik.`
      : `Di ${p.provinsi}, ${persen(p.sma_persen, 1)}% SMA dan ${persen(p.smk_persen, 1)}% SMK sudah berlistrik.`;
  } else if (!kosong) {
    const r = kurang[0];
    const jenis = r.sma_persen <= r.smk_persen ? ["SMA", r.sma_persen] : ["SMK", r.smk_persen];
    teks = `${penuh} dari ${scope.length} provinsi sudah 100%. Terendah: ${jenis[0]} ${r.provinsi}, ${persen(jenis[1], 1)}%.`;
  } else {
    teks = "";
  }
  $("note-sekolah").textContent = teks;
}

mulai().catch((e) => {
  console.error(e);
  $("hero-line").textContent = "Data gagal dimuat. Coba muat ulang halaman.";
});
