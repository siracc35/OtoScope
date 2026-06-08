import { useEffect, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { getTrendBrands, getTrends } from "../api";
import { money } from "../format";

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "var(--surface-2)",
      border: "1px solid var(--border-strong)",
      padding: "10px 14px",
      fontFamily: "var(--mono)",
      fontSize: 12,
    }}>
      <div style={{ color: "var(--text-dim)", marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {money(p.value)} ({p.payload[`${p.name}__count`] ?? 0} ilan)
        </div>
      ))}
    </div>
  );
}

const LINE_COLORS = [
  "#e8ff47", "#38bdf8", "#4ade80", "#f472b6",
  "#fb923c", "#a78bfa", "#34d399", "#f87171",
];

export default function TrendsView() {
  const [brands, setBrands] = useState([]);
  const [selectedBrand, setSelectedBrand] = useState("");
  const [series, setSeries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getTrendBrands().then(setBrands).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedBrand) { setSeries([]); return; }
    setLoading(true);
    setError(null);
    getTrends(selectedBrand)
      .then(setSeries)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedBrand]);

  const allMonths = [...new Set(series.flatMap((s) => s.points.map((p) => p.month)))].sort();
  const chartData = allMonths.map((month) => {
    const row = { month };
    series.forEach((s) => {
      const key = [s.brand, s.model].filter(Boolean).join(" ");
      const pt = s.points.find((p) => p.month === month);
      if (pt) { row[key] = pt.avg_price; row[`${key}__count`] = pt.count; }
    });
    return row;
  });

  const seriesKeys = series.map((s) => [s.brand, s.model].filter(Boolean).join(" "));
  const isEmpty = !loading && series.length === 0 && selectedBrand;
  const noData = !loading && brands.length === 0;
  const totalListings = series.reduce((n, s) => n + s.points.reduce((m, p) => m + p.count, 0), 0);

  return (
    <section>
      <div className="section-title">Fiyat Trendi</div>

      {noData && (
        <div className="empty">
          HENÜZ YETERLİ VERİ YOK — ANALİZ YAPTIKÇA TREND GRAFİĞİ OLUŞUR
        </div>
      )}

      {!noData && (
        <>
          <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 24 }}>
            <select
              value={selectedBrand}
              onChange={(e) => setSelectedBrand(e.target.value)}
              style={{
                background: "var(--surface-2)", color: "var(--text)",
                border: "1px solid var(--border-strong)", padding: "8px 12px",
                fontFamily: "var(--mono)", fontSize: 13, cursor: "pointer", minWidth: 180,
              }}
            >
              <option value="">— Marka seçin —</option>
              {brands.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
            {selectedBrand && (
              <span style={{ color: "var(--text-dim)", fontSize: 12 }}>
                {totalListings} ilan · {allMonths.length} ay
              </span>
            )}
          </div>

          {loading && <div className="loading-line">VERİ YÜKLENİYOR…</div>}
          {error && <div className="banner banner--error">{error}</div>}
          {isEmpty && <div className="empty">BU MARKA İÇİN VERİ YOK</div>}

          {!loading && chartData.length > 0 && (
            <div className="panel" style={{ padding: "24px 8px" }}>
              <div className="label" style={{ marginBottom: 16, paddingLeft: 16 }}>
                ORTALAMA İLAN FİYATI — AYLARA GÖRE
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData} margin={{ top: 8, right: 24, left: 16, bottom: 8 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" />
                  <XAxis dataKey="month" stroke="var(--text-dim)"
                    tick={{ fill: "var(--text-dim)", fontSize: 11, fontFamily: "var(--mono)" }} />
                  <YAxis stroke="var(--text-dim)"
                    tick={{ fill: "var(--text-dim)", fontSize: 11, fontFamily: "var(--mono)" }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-dim)" }} />
                  {seriesKeys.map((key, idx) => (
                    <Line key={key} type="monotone" dataKey={key}
                      stroke={LINE_COLORS[idx % LINE_COLORS.length]} strokeWidth={2}
                      dot={{ r: 3, fill: LINE_COLORS[idx % LINE_COLORS.length] }}
                      activeDot={{ r: 5 }} connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </section>
  );
}
