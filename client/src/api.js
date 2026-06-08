// api.js — the ONLY place the frontend talks to the backend.
// Centralizing fetch calls means base URL / error handling live in one spot.

const API_BASE = "http://127.0.0.1:8000";

// Shared helper: POST/GET JSON and turn non-2xx responses into thrown Errors,
// pulling FastAPI's {detail: ...} message out when present.
async function request(path, options = {}) {
  let resp;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    // Network-level failure (server down, CORS, offline).
    throw new Error("Sunucuya ulaşılamadı. Backend çalışıyor mu? (port 8000)");
  }

  if (!resp.ok) {
    let detail = `Hata ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* response had no JSON body */
    }
    throw new Error(detail);
  }

  return resp.json();
}

export function analyzeListing(text) {
  return request("/api/analyze", { method: "POST", body: JSON.stringify({ text }) });
}

export function getHistory(limit = 50) {
  return request(`/api/history?limit=${limit}`, { method: "GET" });
}

export function scrapeUrl(url) {
  return request("/api/scrape", { method: "POST", body: JSON.stringify({ url }) });
}
