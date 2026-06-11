// api.js — the ONLY place the frontend talks to the backend.
// Centralizing fetch calls means base URL / error handling live in one spot.

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

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
    throw new Error("Sunucuya ulaşılamadı. Backend çalışıyor mu?");
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

export function getHistoryItem(id) {
  return request(`/api/history/${id}`, { method: "GET" });
}

// DELETE returns 204 with no body, so we don't parse JSON here.
export async function deleteHistoryItem(id) {
  const resp = await fetch(`${API_BASE}/api/history/${id}`, { method: "DELETE" });
  if (!resp.ok && resp.status !== 204) {
    throw new Error(`Silme başarısız (hata ${resp.status})`);
  }
}

export function scrapeUrl(url) {
  return request("/api/scrape", { method: "POST", body: JSON.stringify({ url }) });
}

export function getUsage() {
  return request("/api/usage", { method: "GET" });
}

// --- Watchlist ---
export function getWatchlist() {
  return request("/api/watchlist", { method: "GET" });
}

export function addToWatchlist(analysis_id, note = null) {
  return request("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ analysis_id, note }),
  });
}

export function removeFromWatchlist(watchlist_item_id) {
  return fetch(`${API_BASE}/api/watchlist/${watchlist_item_id}`, { method: "DELETE" });
}

export function removeFromWatchlistByAnalysis(analysis_id) {
  return fetch(`${API_BASE}/api/watchlist/by-analysis/${analysis_id}`, { method: "DELETE" });
}

// --- Trends ---
export function getTrends(brand) {
  const q = brand ? `?brand=${encodeURIComponent(brand)}` : "";
  return request(`/api/trends${q}`, { method: "GET" });
}

export function getTrendBrands() {
  return request("/api/trends/brands", { method: "GET" });
}

// --- Model info ---
export function getModelInfo() {
  return request("/api/model/info", { method: "GET" });
}

// --- Batch ---
export function batchAnalyze(texts) {
  return request("/api/batch", { method: "POST", body: JSON.stringify({ texts }) });
}
