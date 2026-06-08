"""
main.py — The application ENTRY POINT.

Narrow responsibility: receive HTTP requests, validate them, route to the right
function, return the result. Business logic (Gemini) does NOT live here -> analyzer.py.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from analyzer import analyze_listing
from models import AnalysisResult, AnalyzeRequest

# The FastAPI application object. title/version show up on the auto-generated /docs page.
app = FastAPI(title="OtoScope API", version="0.1.0")

# ---------------------------------------------------------------------------
# CORS MIDDLEWARE
# ---------------------------------------------------------------------------
# Due to a browser security rule, a request from http://localhost:5173 (React)
# to http://localhost:8000 (FastAPI) counts as a DIFFERENT ORIGIN. Without
# permission the browser blocks it. This middleware declares which origins we
# allow. (We will cover CORS in depth in Phase 2.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server default address
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check — a simple endpoint to confirm the server is up
# ---------------------------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "ok", "service": "OtoScope API"}


# ---------------------------------------------------------------------------
# MAIN ENDPOINT: listing analysis
# ---------------------------------------------------------------------------
# response_model=AnalysisResult -> FastAPI also validates the output against this
# schema and auto-documents it on /docs.
@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(request: AnalyzeRequest) -> AnalysisResult:
    """Take raw listing text, return a structured analysis.

    The moment we write 'request: AnalyzeRequest', FastAPI:
      1. reads the incoming JSON,
      2. VALIDATES it against the AnalyzeRequest schema (invalid -> automatic 422),
      3. if valid, hands us a clean 'request' object.
    So we do NOT write validation code; the type hint is enough.
    """
    result = analyze_listing(request.text)
    return result
