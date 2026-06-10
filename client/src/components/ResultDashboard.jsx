import { useEffect, useRef, useState } from "react";
import { addToWatchlist, getModelInfo, getWatchlist, removeFromWatchlistByAnalysis } from "../api";
import { money, moneySigned, num, verdictMeta } from "../format";

function exportPDF(result) {
  import("jspdf").then(({ jsPDF }) => {
    const doc = new jsPDF({ unit: "mm", format: "a4" });
    const W = 210;
    const MARGIN = 18;
    const COL = W - MARGIN * 2;
    let y = 0;

    const { listing } = result;
    const v = verdictMeta(result.verdict);
    const carName = [listing.brand, listing.model].filter(Boolean).join(" ") || "Araç";
    const now = new Date().toLocaleString("tr-TR");

    function rule(color = [220, 220, 220]) {
      doc.setDrawColor(...color);
      doc.setLineWidth(0.3);
      doc.line(MARGIN, y, W - MARGIN, y);
      y += 4;
    }
    function section(title) {
      y += 2;
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8);
      doc.setTextColor(100, 100, 100);
      doc.text(title.toUpperCase(), MARGIN, y);
      y += 5;
      rule([220, 220, 220]);
    }
    function wrappedText(text, fontSize = 10, color = [40, 40, 40], indent = 0) {
      if (!text) return;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(fontSize);
      doc.setTextColor(...color);
      const lines = doc.splitTextToSize(String(text), COL - indent);
      lines.forEach((line) => {
        if (y > 275) { doc.addPage(); y = MARGIN; }
        doc.text(line, MARGIN + indent, y);
        y += fontSize * 0.45;
      });
      y += 2;
    }
    function keyVal(label, value, valColor = [20, 20, 20]) {
      if (y > 275) { doc.addPage(); y = MARGIN; }
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.setTextColor(110, 110, 110);
      doc.text(label, MARGIN, y);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(9);
      doc.setTextColor(...valColor);
      doc.text(String(value ?? "—"), MARGIN + 52, y);
      y += 6;
    }

    // Header band
    doc.setFillColor(10, 10, 10);
    doc.rect(0, 0, W, 28, "F");

    doc.setFont("helvetica", "bold");
    doc.setFontSize(22);
    doc.setTextColor(232, 255, 71);
    doc.text("OTO", MARGIN, 18);
    const otoW = doc.getTextWidth("OTO");
    doc.setTextColor(255, 255, 255);
    doc.text("SCOPE", MARGIN + otoW, 18);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(120, 120, 120);
    doc.text("İLAN ANALİZ RAPORU", W - MARGIN, 12, { align: "right" });
    doc.text(now, W - MARGIN, 18, { align: "right" });

    y = 36;

    // Verdict + score row
    const verdictColor =
      result.verdict === "DEAL" ? [22, 101, 52]
      : result.verdict === "OVERPRICED" ? [153, 27, 27]
      : [154, 52, 18];

    doc.setDrawColor(...verdictColor);
    doc.setLineWidth(0.8);
    doc.rect(MARGIN, y - 5, 36, 12);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(...verdictColor);
    doc.text(v.label, MARGIN + 18, y + 3, { align: "center" });

    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.setTextColor(20, 20, 20);
    doc.text(carName, MARGIN + 42, y);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(100, 100, 100);
    doc.text(`${listing.year || "—"} MODEL`, MARGIN + 42, y + 6);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(32);
    doc.setTextColor(20, 20, 20);
    doc.text(String(result.opportunity_score), W - MARGIN, y + 2, { align: "right" });
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(100, 100, 100);
    doc.text("/ 100  FIRSAT SKORU", W - MARGIN, y + 8, { align: "right" });

    y += 18;
    rule([180, 180, 180]);

    section("Araç Bilgileri");
    keyVal("Kilometre", num(listing.km) + " km");
    keyVal("Yakıt",     listing.fuel_type || "—");
    keyVal("Vites",     listing.transmission || "—");

    section("Fiyat Analizi");
    keyVal("İlan Fiyatı",    money(listing.listed_price));
    keyVal("Piyasa Aralığı", `${money(result.market_low)} – ${money(result.market_high)}`);
    const diffPos = result.price_diff < 0;
    keyVal(
      "Piyasa Farkı",
      diffPos ? `${money(Math.abs(result.price_diff))} piyasa altı` : moneySigned(result.price_diff),
      diffPos ? [22, 101, 52] : [153, 27, 27],
    );
    if (result.predicted_price) {
      keyVal("Model Tahmini (ML)", money(result.predicted_price));
    }

    if (result.pros?.length) {
      section("Artılar");
      result.pros.forEach((p) => wrappedText(`+ ${p}`, 10, [22, 101, 52]));
    }

    if (result.cons?.length) {
      section("Eksiler / Riskler");
      result.cons.forEach((c) => wrappedText(`– ${c}`, 10, [153, 27, 27]));
    }

    if (result.chronic_issues?.length) {
      section("Kronik Sorunlar");
      result.chronic_issues.forEach((c) => wrappedText(`• ${c}`, 10, [180, 60, 60]));
    }

    if (result.negotiation_guide) {
      section("Pazarlık Rehberi");
      wrappedText(result.negotiation_guide, 10);
    }

    if (result.expert_comment) {
      section("Uzman Yorumu");
      wrappedText(result.expert_comment, 10);
    }

    const pageCount = doc.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(8);
      doc.setTextColor(180, 180, 180);
      doc.text("otoscope · gemini 2.5 flash · scikit-learn", MARGIN, 292);
      doc.text(`${i} / ${pageCount}`, W - MARGIN, 292, { align: "right" });
    }

    const filename = `otoscope-${carName.toLowerCase().replace(/\s+/g, "-")}-${Date.now()}.pdf`;
    doc.save(filename);
  });
}

function ModelInfoBadge() {
  const [info, setInfo] = useState(null);
  useEffect(() => {
    getModelInfo().then(setInfo).catch(() => {});
  }, []);

  if (!info) return null;

  if (!info.trained) {
    return (
      <div style={{ color: "var(--text-faint)", fontSize: 11, marginTop: 4 }}>
        Model henüz eğitilmedi
      </div>
    );
  }

  const parts = [];
  if (info.row_count)  parts.push(`${info.row_count} kayıt`);
  if (info.test_mae)   parts.push(`MAE ₺${Math.round(info.test_mae).toLocaleString("tr-TR")}`);
  if (info.test_r2)    parts.push(`R² ${info.test_r2.toFixed(2)}`);

  return (
    <div style={{ color: "var(--text-dim)", fontSize: 11, marginTop: 4, lineHeight: 1.6 }}>
      {parts.join(" · ")}
    </div>
  );
}

export default function ResultDashboard({ result }) {
  const { listing } = result;
  const v = verdictMeta(result.verdict);
  const dashRef = useRef(null);

  const marketMid = Math.round((result.market_low + result.market_high) / 2);
  const diffPositive = result.price_diff < 0;

  const [watchlistId, setWatchlistId] = useState(null);
  const [watchLoading, setWatchLoading] = useState(false);

  useEffect(() => {
    if (!result.id) return;
    getWatchlist()
      .then((items) => {
        const found = items.find((w) => w.analysis_id === result.id);
        setWatchlistId(found ? found.id : null);
      })
      .catch(() => {});
  }, [result.id]);

  async function toggleWatchlist() {
    if (!result.id) return;
    setWatchLoading(true);
    try {
      if (watchlistId) {
        await removeFromWatchlistByAnalysis(result.id);
        setWatchlistId(null);
      } else {
        const item = await addToWatchlist(result.id);
        setWatchlistId(item.id);
      }
    } catch (err) {
      alert("Favori işlemi başarısız: " + err.message);
    } finally {
      setWatchLoading(false);
    }
  }

  return (
    <section className="dash" ref={dashRef}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>02 / Analiz Sonucu</div>
          {result.id && (
            <span style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--text-faint)", letterSpacing: 1 }}>
              #{String(result.id).padStart(4, "0")}
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }} className="no-print">
          {result.id && (
            <button
              className="btn"
              onClick={toggleWatchlist}
              disabled={watchLoading}
              title={watchlistId ? "Favorilerden çıkar" : "Favorilere kaydet"}
              style={{
                color: watchlistId ? "var(--warning)" : "var(--text-dim)",
                borderColor: watchlistId ? "var(--warning)" : undefined,
              }}
            >
              {watchLoading ? "…" : watchlistId ? "★ Kaydedildi" : "☆ Kaydet"}
            </button>
          )}
          <button className="btn btn--ghost" onClick={() => exportPDF(result)} title="PDF ↓">
            PDF ↓
          </button>
        </div>
      </div>

      <div className="dash__top">
        <div className="panel verdict">
          <div className="verdict__head">
            <span className={`verdict__badge ${v.cls}`}>{v.label}</span>
            <div>
              <div className="verdict__car">
                {[listing.brand, listing.model].filter(Boolean).join(" ") || "Araç"}
              </div>
              <div className="label" style={{ marginTop: 4 }}>
                {listing.year || "—"} Model
              </div>
            </div>
          </div>
          <div className="verdict__meta">
            <span>KM <b>{num(listing.km)}</b></span>
            <span>Yakıt <b>{listing.fuel_type || "—"}</b></span>
            <span>Vites <b>{listing.transmission || "—"}</b></span>
          </div>
        </div>

        <div className="panel score">
          <div className="label">Fırsat Skoru</div>
          <div className="score__num">
            {result.opportunity_score}<small>/100</small>
          </div>
          <div className="score__bar">
            <div
              className="score__fill"
              style={{ width: `${result.opportunity_score}%` }}
              role="progressbar"
              aria-valuenow={result.opportunity_score}
              aria-valuemin="0"
              aria-valuemax="100"
            />
          </div>
        </div>
      </div>

      <div className="prices">
        {/* 1 — İlan fiyatı */}
        <div className="stat stat--primary">
          <div className="stat__label">İlan Fiyatı</div>
          <div className="stat__value stat__value--hero">{money(listing.listed_price)}</div>
          <div className="stat__sub">Satıcı talep fiyatı</div>
        </div>

        {/* 2 — Piyasa aralığı + pozisyon barı */}
        <div className="stat">
          <div className="stat__label">Piyasa Aralığı</div>
          <div className="stat__range">
            <span>{money(result.market_low)}</span>
            <span style={{ color: "var(--text-faint)" }}>–</span>
            <span>{money(result.market_high)}</span>
          </div>
          {listing.listed_price != null && (
            <div className="stat__bar-wrap">
              <div
                className="stat__bar-fill"
                style={{
                  width: `${Math.min(100, Math.max(0,
                    ((listing.listed_price - result.market_low) /
                      Math.max(1, result.market_high - result.market_low)) * 100
                  ))}%`,
                  background: diffPositive ? "var(--positive)" : "var(--danger)",
                }}
              />
            </div>
          )}
          <div className="stat__sub">Orta: {money(marketMid)}</div>
        </div>

        {/* 3 — Piyasa farkı */}
        <div className="stat">
          <div className="stat__label">Piyasa Farkı</div>
          <div className={`stat__value stat__value--lg ${diffPositive ? "stat__value--pos" : "stat__value--neg"}`}>
            {diffPositive
              ? `↓ ${money(Math.abs(result.price_diff))}`
              : `↑ ${money(Math.abs(result.price_diff))}`}
          </div>
          <div className="stat__sub" style={{ color: diffPositive ? "var(--positive)" : "var(--danger)", opacity: 0.8 }}>
            {diffPositive ? "piyasa altında" : "piyasa üstünde"}
          </div>
        </div>

        {/* 4 — ML tahmini */}
        <div className="stat">
          <div className="stat__label">Model Tahmini (ML)</div>
          <div className="stat__value stat__value--lg">
            {result.predicted_price ? money(result.predicted_price) : "—"}
          </div>
          <ModelInfoBadge />
        </div>
      </div>

      <div className="proscons">
        <div className="panel">
          <div className="label" style={{ marginBottom: 12 }}>Artılar</div>
          <ul className="list list--pros">
            {result.pros.length ? result.pros.map((p, i) => <li key={i}>{p}</li>) : <li>—</li>}
          </ul>
        </div>
        <div className="panel">
          <div className="label" style={{ marginBottom: 12 }}>Eksiler / Riskler</div>
          <ul className="list list--cons">
            {result.cons.length ? result.cons.map((c, i) => <li key={i}>{c}</li>) : <li>—</li>}
          </ul>
        </div>
      </div>

      {(result.chronic_issues?.length > 0 || result.user_consensus) && (
        <div className="two-col" style={{ marginTop: 24 }}>
          {result.chronic_issues?.length > 0 && (
            <div className="panel" style={{ borderLeft: "4px solid var(--danger)", backgroundColor: "rgba(239, 68, 68, 0.05)" }}>
              <div className="label" style={{ marginBottom: 12, color: "var(--danger)" }}>
                Kronik Sorunlar
              </div>
              <ul className="list list--cons">
                {result.chronic_issues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            </div>
          )}
          {result.user_consensus && (
            <div className="panel" style={{ borderLeft: "4px solid var(--accent)", backgroundColor: "rgba(56, 189, 248, 0.05)" }}>
              <div className="label" style={{ marginBottom: 12, color: "var(--accent)" }}>
                Kullanıcı Yorumları
              </div>
              <p className="prose">{result.user_consensus}</p>
            </div>
          )}
        </div>
      )}

      <div className="two-col">
        <div className="panel">
          <div className="label" style={{ marginBottom: 12 }}>Pazarlık Rehberi</div>
          <p className="prose">{result.negotiation_guide}</p>
        </div>
        <div className="panel">
          <div className="label" style={{ marginBottom: 12 }}>Uzman Yorumu</div>
          <p className="prose">{result.expert_comment}</p>
        </div>
      </div>
    </section>
  );
}
