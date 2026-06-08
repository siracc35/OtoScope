import { useEffect, useState } from "react";
import { getHistoryItem, getWatchlist, removeFromWatchlist } from "../api";
import { dateTime, money, num, verdictMeta } from "../format";

export default function WatchlistView({ onSelectItem }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [removingId, setRemovingId] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const watchlistItems = await getWatchlist();
        if (!alive) return;
        const enriched = await Promise.all(
          watchlistItems.map(async (w) => {
            try {
              const analysis = await getHistoryItem(w.analysis_id);
              return { ...w, analysis };
            } catch {
              return { ...w, analysis: null };
            }
          })
        );
        if (alive) setItems(enriched);
      } catch (err) {
        if (alive) setError(err.message);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  async function handleRemove(watchlistId) {
    if (!window.confirm("Favorilerden çıkarmak istediğine emin misin?")) return;
    setRemovingId(watchlistId);
    try {
      await removeFromWatchlist(watchlistId);
      setItems((prev) => prev.filter((it) => it.id !== watchlistId));
    } catch (err) {
      setError(err.message);
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <section>
      <div className="section-title">Favori İlanlar</div>

      {loading && (
        <div>
          <div className="scanner" />
          <div className="loading-line">FAVORİLER YÜKLENİYOR…</div>
        </div>
      )}

      {error && !loading && <div className="banner banner--error">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="empty">
          HENÜZ FAVORİ YOK — ANALİZ SONUCUNDA ☆ KAYDET BUTONUNA BASIN
        </div>
      )}

      <div className="history">
        {items.map((it) => {
          const a = it.analysis;
          if (!a) return null;
          const listing = a.listing || a;
          const v = verdictMeta(a.verdict);
          return (
            <article
              className="hist-card"
              key={it.id}
              onClick={() => onSelectItem?.(a)}
              style={onSelectItem ? { cursor: "pointer" } : {}}
            >
              <span className="hist-card__id">#{String(it.analysis_id).padStart(3, "0")}</span>
              <div>
                <div className="hist-card__car">
                  {[listing.brand, listing.model].filter(Boolean).join(" ") || "Araç"}
                </div>
                <div className="hist-card__meta">
                  {listing.year || "—"} · {num(listing.km)} km · {listing.fuel_type || "—"} · skor {a.opportunity_score}
                </div>
                {it.note && (
                  <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 3 }}>
                    📌 {it.note}
                  </div>
                )}
              </div>
              <span className={`chip ${v.cls}`}>{v.label}</span>
              <div>
                <div className="hist-card__price">{money(listing.listed_price)}</div>
                <div className="hist-card__date">{dateTime(it.created_at)}</div>
              </div>
              <button
                className="hist-card__del"
                onClick={(e) => { e.stopPropagation(); handleRemove(it.id); }}
                disabled={removingId === it.id}
                title="Favoriden çıkar"
                aria-label="Favoriden çıkar"
              >
                {removingId === it.id ? "…" : "★"}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
