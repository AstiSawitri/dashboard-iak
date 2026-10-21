// Halaman "Data dan sumber": daftar sumber + penampil isi tabel.
const $ = (id) => document.getElementById(id);
const ANGKA = new Set(["produksi_gwh", "kapasitas_mw", "perkotaan_persen", "perdesaan_persen",
  "total_persen", "negeri_persen", "swasta_persen"]);
const JUDUL_KOLOM = {
  kode_bps: "Kode BPS", provinsi: "Provinsi", wilayah: "Wilayah", tahun: "Tahun",
  produksi_gwh: "Produksi (GWh)", kapasitas_mw: "Kapasitas (MW)",
  perkotaan_persen: "Perkotaan (%)", perdesaan_persen: "Perdesaan (%)", total_persen: "Total (%)",
  negeri_persen: "Negeri (%)", swasta_persen: "Swasta (%)",
};

function sel(tag, text, cls) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}

async function mulai() {
  const meta = await api("/api/meta");
  tulisSumber(meta.sumber);

  const body = document.querySelector("#t-sumber tbody");
  body.innerHTML = "";
  meta.sumber.forEach((s) => {
    const tr = document.createElement("tr");
    const td1 = sel("td"); td1.append(s.nama); if (s.keterangan) td1.append(sel("small", s.keterangan));
    const td2 = sel("td"); td2.append(sel("span", s.format_asal, "fmt"));
    const td3 = sel("td");
    if (s.url) { const a = sel("a", s.sumber); a.href = s.url; a.target = "_blank"; a.rel = "noopener"; td3.append(a); }
    else td3.append(s.sumber);
    tr.append(td1, td2, td3, sel("td", s.tahun_data ?? "", "r"), sel("td", nf0.format(s.jumlah_baris ?? 0), "r"));
    body.append(tr);
  });

  meta.wilayah.forEach((w) => $("ds-wilayah").add(new Option(w, w)));
  ["ds", "ds-wilayah", "ds-nasional"].forEach((id) => $(id).addEventListener("change", tampilkan));
  tampilkan();
}

async function tampilkan() {
  const ds = $("ds").value;
  const q = new URLSearchParams();
  if ($("ds-wilayah").value) q.set("wilayah", $("ds-wilayah").value);
  if ($("ds-nasional").checked) q.set("nasional", "1");
  $("ds-csv").href = `/api/data/${ds}.csv?${q}`;
  const res = await api(`/api/data/${ds}?${q}`);
  const thead = document.querySelector("#t-isi thead");
  const tbody = document.querySelector("#t-isi tbody");
  thead.innerHTML = ""; tbody.innerHTML = "";
  if (!res.data.length) {
    const tr = sel("tr"); const td = sel("td", "Tabel ini masih kosong. Jalankan ETL (Pentaho atau etl_lokal.py) untuk mengisinya."); td.colSpan = 5;
    tr.append(td); tbody.append(tr); $("ds-count").textContent = ""; return;
  }
  const kolom = Object.keys(res.data[0]);
  const hr = sel("tr");
  kolom.forEach((k) => { const th = sel("th", JUDUL_KOLOM[k] || k, ANGKA.has(k) ? "r" : ""); th.scope = "col"; hr.append(th); });
  thead.append(hr);
  res.data.forEach((row) => {
    const tr = sel("tr");
    kolom.forEach((k) => tr.append(sel("td", ANGKA.has(k) ? (row[k] == null ? "kosong" : nf2.format(row[k])) : row[k], ANGKA.has(k) ? "r" : "")));
    tbody.append(tr);
  });
  $("ds-count").textContent = `${nf0.format(res.jumlah)} baris`;
}

mulai().catch((e) => console.error(e));


// ---------------------------------------------------------------- tiga level data + log sinkronisasi
(async function muatEtl() {
  const sel = (q) => document.querySelector(q);
  const sel2 = (id) => document.getElementById(id);
  try {
    const d = await api("/api/etl");
    const td = (txt, cls) => { const c = document.createElement("td"); if (cls) c.className = cls; c.textContent = txt ?? "–"; return c; };
    const lv = sel("#t-level tbody"); lv.innerHTML = "";
    let levelSebelum = "";
    d.lapisan.forEach((x) => {
      const tr = document.createElement("tr");
      tr.append(td(x.level === levelSebelum ? "" : x.level), td(x.tabel), td(nf0.format(x.baris), "r"), td(x.ket || ""));
      if (x.level !== levelSebelum) tr.style.borderTop = "2px solid var(--ink)";
      levelSebelum = x.level;
      lv.append(tr);
    });
    const b = d.batch[0];
    const waktu = (t) => String(t || "").replace("T", " ").slice(0, 16);
    sel2("sinkron-terakhir").textContent = !b ? ""
      : d.mode === "dw"
        ? `Data dimuat oleh ETL Pentaho (schema stg dan dw) pada ${waktu(b.selesai || b.mulai)}.`
        : `Sinkronisasi terakhir: batch ${b.batch_id}, ${waktu(b.selesai || b.mulai)}, ${b.status}, lewat ${b.alat}.`;
    // riwayat: kolom hash hanya kalau ada isinya; bagian disembunyikan kalau belum ada catatan
    const adaHash = d.log.some((x) => x.hash_file);
    if (!adaHash) document.querySelectorAll("#t-log thead th:last-child").forEach((th) => th.remove());
    if (!d.log.length) { const sec = sel("#t-log").closest(".table-wrap"); sec.hidden = true; sec.previousElementSibling.hidden = true; }
    const lg = sel("#t-log tbody"); lg.innerHTML = "";
    d.log.forEach((x) => {
      const tr = document.createElement("tr");
      tr.append(td(waktu(x.waktu)), td(x.batch_id), td(x.tingkat), td(x.dataset), td(x.baris == null ? "" : nf0.format(x.baris), "r"), td(x.status));
      if (adaHash) tr.append(td(x.hash_file ? x.hash_file.slice(0, 12) + "…" : ""));
      if (x.status === "gagal") tr.style.background = "var(--hot)";
      lg.append(tr);
    });
  } catch (e) {
    console.error(e);
  }
})();
