# OtoScope

> AI-powered analysis tool for Turkish used-car listings from sahibinden.com.

OtoScope takes the raw text of a used-car listing, sends it to Google Gemini through
a FastAPI backend, and returns a structured analysis: an estimated market value, an
opportunity score, pros/cons, a negotiation guide, and expert commentary — plus an
independent price estimate from our own scikit-learn model — presented in a
professional, terminal-style dashboard.

## Architecture

```
React (Vite)  ──HTTP──►        FastAPI         ──►  Google Gemini API
  frontend           ┌──────────┼──────────┐         (analyzer.py)
                     ▼          ▼          ▼
                 ml.py     database.py   scraper.py
              scikit-learn   SQLite      BeautifulSoup
```

| Layer         | Responsibility                                               |
|---------------|--------------------------------------------------------------|
| `client/`     | React + Vite UI — presentation only, no secrets              |
| `server/main.py`   | FastAPI — HTTP, validation, routing, persistence        |
| `server/analyzer.py` | Isolated Gemini logic (swap providers in one file)    |
| `server/models.py`   | Pydantic schemas (API) + SQLAlchemy model (DB)        |
| `server/database.py` | Engine, session factory, `get_db` dependency          |
| `server/ml.py`       | scikit-learn price model (train + predict)            |
| `server/scraper.py`  | Optional listing-URL scraping (paste is primary)      |
| SQLite        | Stores past analyses for history and ML training             |

## Tech Stack

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy
- **Frontend:** React + Vite (plain CSS design system, no UI framework)
- **AI:** Google Gemini (`gemini-2.5-flash`) via `google-genai`, structured output
- **ML:** scikit-learn (RandomForest) — price prediction
- **Scraping:** requests + BeautifulSoup
- **Database:** SQLite

## Getting Started

### 1. Backend

```bash
# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate          # macOS / Linux

# Install dependencies
pip install -r server/requirements.txt

# Configure your API key
cp server/.env.example server/.env   # then edit server/.env -> GEMINI_API_KEY=...

# (Optional) train the price model — bootstraps on synthetic data
python server/ml.py train

# Run the API
uvicorn main:app --app-dir server --reload
```

API at `http://127.0.0.1:8000`, interactive docs at `http://127.0.0.1:8000/docs`.

### 2. Frontend

```bash
cd client
npm install
npm run dev          # http://localhost:5173
```

## API

| Method | Path                  | Description                                   |
|--------|-----------------------|-----------------------------------------------|
| `GET`  | `/`                   | Health check                                  |
| `POST` | `/api/analyze`        | Analyze raw listing text → full analysis      |
| `GET`  | `/api/history`        | List past analyses (newest first)             |
| `GET`  | `/api/history/{id}`   | A single past analysis                        |
| `POST` | `/api/scrape`         | Fetch a listing URL → raw text (best-effort)  |
| `POST` | `/api/predict`        | ML price estimate from a feature vector       |

## Project Status

- [x] Phase 1 — Backend core (FastAPI, Pydantic, SQLite, Gemini)
- [x] Phase 2 — React frontend & terminal-style dashboard
- [x] Phase 3 — History page & scraping
- [x] Phase 4 — ML price prediction (scikit-learn)

## License

For educational purposes.
