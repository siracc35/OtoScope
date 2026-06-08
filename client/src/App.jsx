import { useEffect, useState } from "react";
import { analyzeListing, getHistoryItem, getUsage } from "./api";
import AnalyzeForm from "./components/AnalyzeForm";
import BatchAnalyzeView from "./components/BatchAnalyzeView";
import CompareView from "./components/CompareView";
import HistoryView from "./components/HistoryView";
import ResultDashboard from "./components/ResultDashboard";
import TrendsView from "./components/TrendsView";
import WatchlistView from "./components/WatchlistView";

function normalizeResult(data) {
  if (!data) return null;
  if (data.listing) return data;
  return {
    ...data,
    listing: {
      brand: data.brand,
      model: data.model,
      year: data.year,
      km: data.km,
      fuel_type: data.fuel_type,
      transmission: data.transmission,
      listed_price: data.listed_price,
    },
  };
}

const VIEWS = ["analyze", "history", "watchlist", "compare", "trends", "batch"];

export default function App() {
  const [view, setView] = useState("analyze");
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [usage, setUsage] = useState(null);

  useEffect(() => {
    getUsage().then(setUsage).catch(() => {});
  }, []);

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("id");
    if (!id) return;
    getHistoryItem(id)
      .then((item) => { setResult(normalizeResult(item)); setView("analyze"); })
      .catch(() => {});
    window.history.replaceState({}, "", "/");
  }, []);

  const [theme, setTheme] = useState(() => localStorage.getItem("otoscope-theme") || "dark");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("otoscope-theme", theme);
  }, [theme]);

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeListing(text);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      getUsage().then(setUsage).catch(() => {});
    }
  }

  const NAV_LABELS = {
    analyze:   "Analiz",
    history:   "Geçmiş",
    watchlist: "Favoriler",
    compare:   "Karşılaştır",
    trends:    "Trend",
    batch:     "Toplu",
  };

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand__mark">OTO<b>SCOPE</b></span>
          <span className="brand__sub">
            İlan Analiz Terminali
            {usage && (
              <span className="brand__quota">
                {usage.exempt
                  ? " · SINIRSIZ (OPERATÖR)"
                  : ` · BUGÜN ${usage.used}/${usage.limit} ANALİZ`}
              </span>
            )}
          </span>
        </div>
        <nav className="nav">
          {VIEWS.map((v) => (
            <button
              key={v}
              className={`nav__btn ${view === v ? "nav__btn--active" : ""}`}
              onClick={() => setView(v)}
            >
              {NAV_LABELS[v]}
            </button>
          ))}
          <button
            className="nav__btn"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title="Temayı değiştir"
          >
            {theme === "dark" ? "☀ Açık" : "☾ Koyu"}
          </button>
        </nav>
      </header>

      {view === "analyze" && (
        <>
          <AnalyzeForm
            text={text}
            setText={setText}
            onAnalyze={handleAnalyze}
            loading={loading}
            error={error}
          />
          {result && (
            <div style={{ marginTop: 36 }}>
              <ResultDashboard result={result} />
            </div>
          )}
        </>
      )}

      {view === "history" && (
        <HistoryView
          onSelectItem={async (item) => {
            try {
              const fullItem = await getHistoryItem(item.id);
              setResult(normalizeResult(fullItem));
              setView("analyze");
            } catch (err) {
              alert("Analiz detayı yüklenirken bir hata oluştu: " + err.message);
            }
          }}
        />
      )}

      {view === "watchlist" && (
        <WatchlistView
          onSelectItem={(item) => {
            setResult(normalizeResult(item));
            setView("analyze");
          }}
        />
      )}

      {view === "compare" && (
        <CompareView
          onSelectItem={(item) => {
            setResult(normalizeResult(item));
            setView("analyze");
          }}
        />
      )}

      {view === "trends" && <TrendsView />}

      {view === "batch" && (
        <BatchAnalyzeView
          onSelectResult={(r) => {
            setResult(r);
            setView("analyze");
          }}
        />
      )}

      <footer className="footer">
        <span>OTOSCOPE © 2026 — GEMINI 2.5 FLASH · FASTAPI · SCIKIT-LEARN</span>
        <span>SAHİBİNDEN.COM İLAN ANALİZİ</span>
      </footer>
    </div>
  );
}
