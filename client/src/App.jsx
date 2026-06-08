import { useState } from "react";
import { analyzeListing } from "./api";
import AnalyzeForm from "./components/AnalyzeForm";
import ResultDashboard from "./components/ResultDashboard";
import HistoryView from "./components/HistoryView";

// App is the single source of truth for the analyze flow. Note the THREE
// separate state values: `loading`, `error`, and `result`. We keep them apart
// (instead of one "status" blob) because each drives a different part of the
// UI independently — the form can show a loading bar while an OLD result is
// still on screen, and an error must not erase a previous result.
export default function App() {
  const [view, setView] = useState("analyze"); // 'analyze' | 'history'
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand__mark">OTO<b>SCOPE</b></span>
          <span className="brand__sub">İlan Analiz Terminali</span>
        </div>
        <nav className="nav">
          <button
            className={`nav__btn ${view === "analyze" ? "nav__btn--active" : ""}`}
            onClick={() => setView("analyze")}
          >
            Analiz
          </button>
          <button
            className={`nav__btn ${view === "history" ? "nav__btn--active" : ""}`}
            onClick={() => setView("history")}
          >
            Geçmiş
          </button>
        </nav>
      </header>

      {view === "analyze" ? (
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
      ) : (
        <HistoryView />
      )}

      <footer className="footer">
        <span>OTOSCOPE © 2026 — GEMINI 2.5 FLASH · FASTAPI · SCIKIT-LEARN</span>
        <span>SAHIBINDEN.COM İLAN ANALİZİ</span>
      </footer>
    </div>
  );
}
