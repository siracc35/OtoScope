import { useEffect, useMemo, useState } from "react";
import { getHistory, getHistoryItem } from "../api";
import { money, num, verdictMeta } from "../format";

const MAX_COMPARE = 3;

export default function CompareView({ onSelectItem }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [records, setRecords] = useState([]);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await getHistory();
        if (alive) setItems(data);
      } catch (err) {
        if (alive) setError(err.message);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  function toggle(id) {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= MAX_COMPARE) return prev;
      return [...prev, id];
    });
  }

  async function runCompare() {
    setComparing(true);
    setError(null);
    try {
      const full = await Promise.all(selectedIds.map((id) => getHistoryItem(id)));
      setRecords(full);
    } catch (err) {
      setError(err.message);
    } finally {
      setComparing(false);
    }
  }

  function priceDiffDisplay(diff) {
    if (diff === null || diff === undefined) return "—";
    if (diff < 0) return `${money(Math.abs(diff))} altı`;
    if (diff > 0) return `+${money(diff)} üstü`;
    return "Eşit";
  }

  const ROWS = useMemo(() => [
    ["Araç",         (r) => [r.listing.brand, r.listing.model].filter(Boolean).join(" ") || "—", null],
    ["Yıl",          (r) => r.listing.year,          "high"],
    ["KM",           (r) => r.listing.km,             "low",  (v) => v != null ? num(v) + " km" : "—"],
    ["Yakıt",        (r) => r.listing.fuel_type || "—", null],
    ["Vites",        (r) => r.listing.transmission || "—", null],
    ["İlan Fiyatı",  (r) => r.listing.listed_price,  null,   money],
    ["Fırsat Skoru", (r) => r.opportunity_score,     "high"],
    ["Piyasa Alt",   (r) => r.market_low,            null,   money],
    ["Piyasa Üst",   (r) => r.market_high,           null,   money],
    ["Piyasa Farkı", (r) => r.price_diff,            "low",  priceDiffDisplay],
    ["Model Tahmini",(r) => r.predicted_price,       null,   money],
  ], []);

  function bestIndex(accessor, dir) {
    if (!dir) return -1;
    let bestVal = dir === "high" ? -Infinity : Infinity;
    let bestIdx = -1;
    let tie = false;
    records.forEach((r, i) => {
      const val = accessor(r);
      if (typeof val !== "number") return;
      if ((dir === "high" && val > bestVal) || (dir === "low" && val < bestVal)) {
        bestVal = val; bestIdx = i; tie = false;
      } else if (val === bestVal) {
        tie = true;
      }
    });
    return tie ? -1 : bestIdx;
  }

  return (
    <section>
      <div className="section-title">Karşılaştır</div>

      {loading && (
        <div>
          <div className="scanner" />
          <div className="loading-line">GEÇMİŞ YÜKLENİYOR…</div>
        </div>
      )}

      {error && !loading && <div className="banner banner--error">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="empty">HENÜZ ANALİZ YOK — KARŞILAŞTIRMAK İÇİN EN AZ 2 ANALİZ YAPINIZ</div>
      )}

      {!loading && items.length > 0 && (
        <>
          <div className="label" style={{ marginBottom: 12 }}>
            {selectedIds.length} / {MAX_COMPARE} seçildi — karşılaştırmak için 2 veya 3 ilan seçin
          </div>

          <div className="history" style={{ marginBottom: 20 }}>
            {items.map((it) => {
              const v = verdictMeta(it.verdict);
              const checked = selectedIds.includes(it.id);
              const disabled = !checked && selectedIds.length >= MAX_COMPARE;
              return (
                <article
                  className="hist-card"
                  key={it.id}
                  onClick={() => !disabled && toggle(it.id)}
                  style={{
                    cursor: disabled ? "not-allowed" : "pointer",
                    opacity: disabled ? 0.4 : 1,
                    borderColor: checked ? "var(--accent)" : undefined,
                  }}
                >
                  <span className="hist-card__id">{checked ? "✓" : "○"}</span>
                  <div>
                    <div className="hist-card__car">
                      {[it.brand, it.model].filter(Boolean).join(" ") || "Araç"}
                    </div>
                    <div className="hist-card__meta">
                      {it.year || "—"} · {num(it.km)} km · {it.fuel_type || "—"} · skor {it.opportunity_score}
                    </div>
                  </div>
                  <span className={`chip ${v.cls}`}>{v.label}</span>
                  <div>
                    <div className="hist-card__price">{money(it.listed_price)}</div>
                  </div>
                </article>
              );
            })}
          </div>

          <button
            className="btn btn--primary"
            onClick={runCompare}
            disabled={selectedIds.length < 2 || comparing}
          >
            {comparing ? "Karşılaştırılıyor…" : `${selectedIds.length} İlanı Karşılaştır →`}
          </button>
        </>
      )}

      {records.length >= 2 && (
        <div className="panel" style={{ marginTop: 28, overflowX: "auto" }}>
          <table className="compare-table">
            <thead>
              <tr>
                <th></th>
                {records.map((r) => {
                  const v = verdictMeta(r.verdict);
                  return (
                    <th key={r.id}>
                      <span
                        className={`chip ${v.cls}`}
                        onClick={() => onSelectItem?.(r)}
                        style={{ cursor: "pointer" }}
                        title="Analiz sonucunu gör"
                      >
                        #{String(r.id).padStart(3, "0")} {v.label}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {ROWS.map(([label, accessor, dir, fmt]) => {
                const best = bestIndex(accessor, dir);
                return (
                  <tr key={label}>
                    <td className="compare-table__label">{label}</td>
                    {records.map((r, i) => {
                      const raw = accessor(r);
                      const display = fmt ? fmt(raw) : raw ?? "—";
                      return (
                        <td
                          key={r.id}
                          style={i === best ? { color: "var(--positive)", fontWeight: 700 } : undefined}
                        >
                          {display}{i === best && " ★"}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
