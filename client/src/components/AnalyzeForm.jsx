import { useState } from "react";
import { scrapeUrl } from "../api";

// The input surface: paste listing text (primary) OR try to scrape a URL.
// loading / error are passed down from App so the three render states
// (idle, loading, error) stay explicit and separate.
export default function AnalyzeForm({ text, setText, onAnalyze, loading, error }) {
  const [url, setUrl] = useState("");
  const [scraping, setScraping] = useState(false);
  const [scrapeMsg, setScrapeMsg] = useState(null);

  async function handleScrape() {
    if (!url.trim()) return;
    setScraping(true);
    setScrapeMsg(null);
    try {
      const data = await scrapeUrl(url.trim());
      setText(data.text);
      setScrapeMsg(null);
    } catch (err) {
      // sahibinden usually blocks bots — show the message, paste still works.
      setScrapeMsg(err.message);
    } finally {
      setScraping(false);
    }
  }

  const canAnalyze = text.trim().length > 0 && !loading;

  return (
    <section>
      <div className="section-title">01 / İlan Girişi</div>

      {/* Optional convenience: pull text from a URL. Paste is the reliable path. */}
      <div className="form__bar">
        <input
          className="input"
          type="text"
          placeholder="https://www.sahibinden.com/ilan/... (opsiyonel — çekmeyi dener)"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={scraping || loading}
        />
        <button className="btn btn--ghost" onClick={handleScrape} disabled={scraping || loading || !url.trim()}>
          {scraping ? "Çekiliyor…" : "URL'den Çek"}
        </button>
      </div>

      {scrapeMsg && <div className="banner banner--info">{scrapeMsg}</div>}

      <textarea
        className="textarea"
        placeholder="sahibinden.com ilan sayfasının tüm metnini buraya yapıştırın…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={loading}
      />

      <div className="form__footer">
        <span className="char-count">{text.length.toLocaleString("tr-TR")} karakter</span>
        <button className="btn" onClick={onAnalyze} disabled={!canAnalyze}>
          {loading ? "Analiz Ediliyor…" : "Analiz Et →"}
        </button>
      </div>

      {/* LOADING state — distinct from idle/error */}
      {loading && (
        <div style={{ marginTop: 18 }}>
          <div className="scanner" />
          <div className="loading-line">GEMINI İLANI DEĞERLENDİRİYOR — PİYASA TARANIYOR…</div>
        </div>
      )}

      {/* ERROR state — distinct from loading/success */}
      {error && !loading && <div className="banner banner--error" style={{ marginTop: 18 }}>{error}</div>}
    </section>
  );
}
