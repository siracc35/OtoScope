import { useState } from "react";
import { login, register, setToken } from "../api";

export default function AuthModal({ onSuccess, onClose }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const fn = mode === "login" ? login : register;
      const data = await fn(email.trim(), password);
      setToken(data.token);
      onSuccess({ id: data.user_id, email: data.email });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <span className="section-title" style={{ marginBottom: 0, border: "none", padding: 0 }}>
            {mode === "login" ? "Giriş Yap" : "Hesap Oluştur"}
          </span>
          <button className="modal__close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <div className="label" style={{ marginBottom: 6 }}>Email</div>
            <input
              className="input"
              type="email"
              placeholder="ornek@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
              autoFocus
              style={{ width: "100%" }}
            />
          </div>
          <div>
            <div className="label" style={{ marginBottom: 6 }}>Şifre</div>
            <input
              className="input"
              type="password"
              placeholder={mode === "register" ? "En az 6 karakter" : "Şifreniz"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              style={{ width: "100%" }}
            />
          </div>

          {error && <div className="banner banner--error">{error}</div>}

          <button className="btn" type="submit" disabled={loading || !email || !password}>
            {loading ? "Bekleniyor…" : mode === "login" ? "Giriş Yap" : "Kayıt Ol"}
          </button>
        </form>

        <div style={{ marginTop: 16, textAlign: "center", fontSize: 12, color: "var(--text-dim)" }}>
          {mode === "login" ? (
            <>Hesabın yok mu?{" "}
              <button className="link-btn" onClick={() => { setMode("register"); setError(null); }}>
                Kayıt ol
              </button>
            </>
          ) : (
            <>Zaten hesabın var mı?{" "}
              <button className="link-btn" onClick={() => { setMode("login"); setError(null); }}>
                Giriş yap
              </button>
            </>
          )}
        </div>

        {mode === "login" && (
          <div style={{ marginTop: 12, fontSize: 11, color: "var(--text-faint)", textAlign: "center" }}>
            Giriş yapınca günlük analiz hakkın artar.
          </div>
        )}
      </div>
    </div>
  );
}
