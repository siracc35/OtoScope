# OtoScope — AI-Powered Used Car Analysis

> Paste a Turkish used car listing → get an instant AI valuation, market comparison, and negotiation guide.

**Live:** https://otoscope-production.up.railway.app

---

## What it does

OtoScope analyzes used car listings using a combination of large language models and a machine learning price model. Paste the listing text and get:

- **Verdict** — DEAL / FAIR / OVERPRICED with an opportunity score (0–100)
- **Market range** — estimated low and high for that car in the current market
- **Price delta** — how far the listing is from the market midpoint
- **Pros / cons** — extracted from the listing and cross-referenced with known model issues
- **Negotiation guide** — concrete talking points to bring the price down
- **Chronic issues** — known reliability problems for that specific model

---

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, SQLAlchemy, PostgreSQL |
| AI | Google Gemini 2.5 Flash |
| ML | scikit-learn RandomForest (price prediction, retrains on accumulated data) |
| Frontend | React, Vite |
| Auth | Email + password, JWT (30-day sessions) |
| Browser | Chrome Extension (Manifest V3) |
| Hosting | Railway |

---

## Architecture

```
Browser / Extension
      │
      ▼
React Frontend (Vite)
      │  REST
      ▼
FastAPI Backend
  ├── Gemini 2.5 Flash  →  structured analysis (verdict, pros/cons, negotiation)
  ├── scikit-learn       →  price prediction from listing features
  └── PostgreSQL         →  persist analyses, users, rate limits
```

The ML model bootstraps on first run and retrains automatically every 5 new analyses once real data accumulates.

---

## Features

- URL or text input — paste a listing URL or raw text
- History — all past analyses saved and searchable
- Watchlist — save listings to revisit
- Compare — side-by-side comparison of multiple analyses
- Trends — price history charts by brand/model
- Batch analysis — analyze up to 10 listings at once
- Chrome Extension — one-click analysis from any supported listing page
- Dark / light theme
- Rate limiting — 3/day guests, 100/day registered users

---

## Local development

```bash
# Backend
cd server
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
# create .env with GEMINI_API_KEY=your_key
uvicorn main:app --reload --port 8000

# Frontend
cd client
npm install
npm run dev
```

---

## Environment variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio key |
| `DATABASE_URL` | PostgreSQL connection string (defaults to local SQLite) |
| `JWT_SECRET` | Secret for signing JWT tokens |
| `RATE_LIMIT_PER_IP` | Guest daily cap (default: 3) |
| `RATE_LIMIT_PER_USER` | Registered user daily cap (default: 100) |
