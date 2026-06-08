# OtoScope

> AI-powered analysis tool for Turkish used-car listings from sahibinden.com.

OtoScope takes the raw text of a used-car listing, sends it to Google Gemini through
a FastAPI backend, and returns a structured analysis: an estimated market value, an
opportunity score, a negotiation guide, and expert commentary — presented in a
professional, terminal-style dashboard.

## Architecture

```
React (Vite)  ──HTTP──►  FastAPI  ──►  Google Gemini API
   frontend               backend
                             │
                             ▼
                       SQLite (history)
```

| Layer        | Responsibility                                              |
|--------------|-------------------------------------------------------------|
| `client/`    | React + Vite UI — presentation only, no secrets             |
| `server/`    | FastAPI — HTTP, validation, routing                         |
| `analyzer.py`| Isolated Gemini logic (swap providers by editing one file) |
| `models.py`  | Pydantic schemas + (later) SQLAlchemy models               |
| SQLite       | Stores past analyses for history and future ML training     |

## Tech Stack

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy
- **Frontend:** React + Vite (added in Phase 2)
- **AI:** Google Gemini (`gemini-2.5-flash`) via `google-genai`
- **Database:** SQLite

## Getting Started (Backend)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate          # macOS / Linux

# 2. Install dependencies
pip install -r server/requirements.txt

# 3. Configure your API key
cp server/.env.example server/.env   # then edit server/.env
# set GEMINI_API_KEY=...

# 4. Run the API
uvicorn main:app --app-dir server --reload
```

The API is then available at `http://127.0.0.1:8000` and interactive docs at
`http://127.0.0.1:8000/docs`.

## API

| Method | Path            | Description                                |
|--------|-----------------|--------------------------------------------|
| `GET`  | `/`             | Health check                               |
| `POST` | `/api/analyze`  | Analyze raw listing text, return analysis  |

## Project Status

Built incrementally as a learning project.

- [x] Phase 1 — Backend core (FastAPI, endpoint, Pydantic, SQLite, Gemini)
- [ ] Phase 2 — React frontend & dashboard
- [ ] Phase 3 — History page & scraping
- [ ] Phase 4 — ML price prediction (scikit-learn)

## License

For educational purposes.
