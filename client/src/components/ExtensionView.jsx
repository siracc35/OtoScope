import { useState } from "react";
import { getToken } from "../api";

const STEPS = [
  {
    n: "1",
    title: "ZIP'i İndir",
    desc: "Aşağıdaki butona bas, dosya bilgisayarına inecek.",
  },
  {
    n: "2",
    title: "ZIP'i Aç",
    desc: 'İnen "otoscope-extension.zip" dosyasına çift tıkla ve içindeki klasörü bir yere çıkar.',
  },
  {
    n: "3",
    title: "Chrome Uzantılar Sayfasını Aç",
    desc: (
      <>
        Chrome adres çubuğuna yapıştır:{" "}
        <code className="ext-code">chrome://extensions</code> → Enter
      </>
    ),
  },
  {
    n: "4",
    title: "Geliştirici Modunu Aç",
    desc: 'Sağ üst köşedeki "Geliştirici modu" toggle\'ını aç (mavi olacak).',
  },
  {
    n: "5",
    title: "Klasörü Yükle",
    desc: '"Paketlenmemiş öğe yükle" butonuna bas → ZIP\'ten çıkardığın klasörü seç → Aç.',
  },
  {
    n: "6",
    title: "Bitti!",
    desc: "Chrome sağ üstünde OtoScope simgesi çıkar. Sahibinden veya arabam.com\'da herhangi bir ilana gir, simgeye tıkla → otomatik analiz eder.",
  },
];

export default function ExtensionView() {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    try {
      const token = getToken();
      const resp = await fetch("/api/extension/download", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) throw new Error(`İndirme başarısız (${resp.status})`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "otoscope-extension.zip";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section>
      <div className="section-title">Chrome Extension</div>

      <div className="panel" style={{ marginBottom: 24 }}>
        <p style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 16, lineHeight: 1.6 }}>
          Sahibinden.com veya arabam.com'da bir ilana girdiğinde tek tıkla analiz eder —
          kopyala yapıştır yok, link aramak yok.
        </p>
        <button className="btn" onClick={handleDownload} disabled={downloading}>
          {downloading ? "İndiriliyor…" : "Extension'ı İndir →"}
        </button>
        {error && <div className="banner banner--error" style={{ marginTop: 12 }}>{error}</div>}
      </div>

      <div className="section-title">Kurulum Adımları</div>
      <div className="ext-steps">
        {STEPS.map((s) => (
          <div key={s.n} className="ext-step">
            <div className="ext-step__num">{s.n}</div>
            <div className="ext-step__body">
              <div className="ext-step__title">{s.title}</div>
              <div className="ext-step__desc">{s.desc}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="banner banner--info" style={{ marginTop: 24 }}>
        Sadece <strong>Google Chrome</strong> ve Chromium tabanlı tarayıcılarda çalışır
        (Edge, Brave, Opera). Safari ve Firefox desteklenmiyor.
      </div>
    </section>
  );
}
