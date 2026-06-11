import { useState } from "react";
import { scrapeUrl } from "../api";

const SUPPORTED_SITES = ["arabam.com", "araba.com", "otosor.com.tr", "otoplus.com.tr", "fordikinciel.com", "sahibinden.com*", "shbd.io (mobil)"];

export default function AnalyzeForm({ text, setText, onAnalyze, loading, error }) {
  const [url, setUrl] = useState("");
  const [scraping, setScraping] = useState(false);
  const [scrapeMsg, setScrapeMsg] = useState(null);

  const [scrapeInfo, setScrapeInfo] = useState(false); // true = show paste hint

  async function handleScrapeAndAnalyze() {
    if (!url.trim()) return;
    setScraping(true);
    setScrapeMsg(null);
    setScrapeInfo(false);
    try {
      const data = await scrapeUrl(url.trim());
      setText(data.text);
      await onAnalyze(data.text);
    } catch (err) {
      if (err.message === "SAHIBINDEN_BLOCKED") {
        setScrapeInfo(true);
      } else {
        setScrapeMsg(err.message);
      }
    } finally {
      setScraping(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") handleScrapeAndAnalyze();
  }

  const busy = scraping || loading;
  const canAnalyze = text.trim().length > 0 && !busy;

  return (
    <section>
      <div className="section-title">01 / İlan Girişi</div>

      {/* URL ile direkt analiz */}
      <div className="form__bar">
        <input
          className="input"
          type="url"
          placeholder="İlan URL'sini yapıştır…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={busy}
        />
        <button
          className="btn"
          onClick={handleScrapeAndAnalyze}
          disabled={busy || !url.trim()}
        >
          {scraping ? "Çekiliyor…" : loading ? "Analiz…" : "Analiz Et →"}
        </button>
      </div>

      {scrapeMsg && <div className="banner banner--error">{scrapeMsg}</div>}

      {scrapeInfo && (
        <div className="banner banner--info" style={{ lineHeight: 1.6 }}>
          <strong>sahibinden.com otomatik erişimi engelliyor.</strong><br />
          İlanı açık, <kbd>Ctrl+A</kbd> → <kbd>Ctrl+C</kbd> yapıp aşağıdaki alana yapıştırın — analiz çalışır.
        </div>
      )}

      {/* Manuel metin girişi */}
      <div className="section-title" style={{ marginTop: 8 }}>veya metni yapıştır</div>
      <textarea
        className="textarea"
        placeholder="İlan sayfasının tüm metnini buraya kopyalayıp yapıştırabilirsiniz…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={busy}
      />

      <div className="form__footer">
        <span className="char-count">{text.length.toLocaleString("tr-TR")} karakter</span>
        <button className="btn" onClick={() => onAnalyze()} disabled={!canAnalyze}>
          {loading ? "Analiz Ediliyor…" : "Analiz Et →"}
        </button>
      </div>

      {loading && (
        <div style={{ marginTop: 18 }}>
          <div className="scanner" />
          <div className="loading-line">GEMİNİ İLANI DEĞERLENDİRİYOR — PİYASA TARANIYOR…</div>
        </div>
      )}

      {error && !loading && <div className="banner banner--error" style={{ marginTop: 18 }}>{error}</div>}
    </section>
  );
}
