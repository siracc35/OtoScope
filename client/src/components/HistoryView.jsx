import { useEffect, useState } from "react";
import { getHistory } from "../api";
import { dateTime, money, num, verdictMeta } from "../format";

// Self-contained view: owns its own load/error/data lifecycle.
export default function HistoryView() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section>
      <div className="section-title">Geçmiş Analizler</div>

      {loading && (
        <div>
          <div className="scanner" />
          <div className="loading-line">KAYITLAR YÜKLENİYOR…</div>
        </div>
      )}

      {error && !loading && <div className="banner banner--error">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="empty">HENÜZ KAYITLI ANALİZ YOK — İLK İLANINI ANALİZ ET</div>
      )}

      <div className="history">
        {items.map((it) => {
          const v = verdictMeta(it.verdict);
          return (
            <article className="hist-card" key={it.id}>
              <span className="hist-card__id">#{String(it.id).padStart(3, "0")}</span>
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
                <div className="hist-card__date">{dateTime(it.created_at)}</div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
