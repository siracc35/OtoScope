import { useState } from "react";
import { batchAnalyze } from "../api";
import { money, verdictMeta } from "../format";

const SEPARATOR = "---";

export default function BatchAnalyzeView({ onSelectResult }) {
  const [rawText, setRawText] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const texts = rawText.split(SEPARATOR).map((t) => t.trim()).filter(Boolean);

  async function handleBatch() {
    if (texts.length === 0) return;
    if (texts.length > 10) { setError("En fazla 10 ilan analiz edilebilir."); return; }
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      const data = await batchAnalyze(texts);
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <div className="section-title">Toplu Analiz</div>

      <div className="panel" style={{ marginBottom: 24 }}>
        <div className="label" style={{ marginBottom: 12 }}>
          Her ilanı <code>---</code> ile ayırın (en fazla 10 ilan)
        </div>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder={"1. ilan metni buraya...\n---\n2. ilan metni buraya...\n---\n3. ilan metni buraya..."}
          rows={12}
          style={{
            width: "100%",
            background: "var(--surface-2)",
            color: "var(--text)",
            border: "1px solid var(--border-strong)",
            padding: "12px",
            fontFamily: "var(--mono)",
            fontSize: 13,
            resize: "vertical",
            lineHeight: 1.6,
          }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
          <span style={{ color: "var(--text-dim)", fontSize: 12 }}>
            {texts.length} ilan{texts.length > 10 ? " · Limit aşıldı (max 10)" : ""}
          </span>
          <button
            className="btn btn--primary"
            onClick={handleBatch}
            disabled={loading || texts.length === 0 || texts.length > 10}
          >
            {loading ? "Analiz ediliyor…" : `${texts.length} İlanı Analiz Et →`}
          </button>
        </div>
      </div>

      {error && <div className="banner banner--error">{error}</div>}

      {loading && (
        <div>
          <div className="scanner" />
          <div className="loading-line">İLANLAR ANALİZ EDİLİYOR — LÜTFEN BEKLEYİN…</div>
        </div>
      )}

      {results.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="label" style={{ marginBottom: 4 }}>
            {results.filter((r) => r.success).length} / {results.length} BAŞARILI
          </div>
          {results.map((item) => {
            if (!item.success) {
              return (
                <div key={item.index} className="panel" style={{ borderLeft: "4px solid var(--danger)", opacity: 0.7 }}>
                  <span style={{ color: "var(--danger)" }}>
                    İlan {item.index + 1} — Hata: {item.error}
                  </span>
                </div>
              );
            }
            const r = item.result;
            const listing = r.listing;
            const v = verdictMeta(r.verdict);
            return (
              <article
                key={item.index}
                className="hist-card"
                onClick={() => onSelectResult?.(r)}
                style={{ cursor: onSelectResult ? "pointer" : "default" }}
              >
                <span className="hist-card__id">#{item.index + 1}</span>
                <div>
                  <div className="hist-card__car">
                    {[listing.brand, listing.model].filter(Boolean).join(" ") || "Araç"}
                  </div>
                  <div className="hist-card__meta">
                    {listing.year || "—"} · {listing.km?.toLocaleString()} km · {listing.fuel_type || "—"} · skor {r.opportunity_score}
                  </div>
                </div>
                <span className={`chip ${v.cls}`}>{v.label}</span>
                <div>
                  <div className="hist-card__price">{money(listing.listed_price)}</div>
                  <div className="hist-card__date" style={{ color: "var(--text-dim)" }}>
                    Piyasa: {money(r.market_low)} – {money(r.market_high)}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
