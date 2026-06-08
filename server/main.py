"""
main.py — The application ENTRY POINT.

Narrow responsibility: receive HTTP requests, validate them, route to the right
module, persist results, return JSON. Business logic lives elsewhere:
  - analyzer.py  -> Gemini
  - ml.py        -> price prediction
  - scraper.py   -> page fetching
  - database.py  -> sessions

A note on async vs sync: our Gemini, DB and scraping libraries are SYNCHRONOUS
(blocking). If we declared these endpoints `async def`, those blocking calls
would freeze the event loop and stall other requests. By declaring them plain
`def`, FastAPI runs each one in a worker THREAD POOL, so one slow Gemini call
no longer blocks everyone else. Right tool for blocking I/O.
"""

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from analyzer import analyze_listing
from database import Base, engine, get_db
from ml import predict_price
from models import (
    AnalysisRecord,
    AnalysisResult,
    AnalyzeRequest,
    HistoryItem,
    PredictRequest,
    PredictResponse,
    ScrapeRequest,
    ScrapeResponse,
    UsageStatus,
)
from ratelimit import client_ip, enforce_limits, record_usage, usage_status
from scraper import ScrapeError, scrape_listing

# Create the table(s) on startup if they don't exist yet.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="OtoScope API", version="1.0.0")

# CORS: allow the Vite dev server (and its 127.0.0.1 alias) to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "OtoScope API"}


# ---------------------------------------------------------------------------
# ANALYZE: Gemini analysis + ML prediction + persist to SQLite
# ---------------------------------------------------------------------------
@app.post("/api/analyze", response_model=AnalysisResult)
def analyze(
    payload: AnalyzeRequest, request: Request, db: Session = Depends(get_db)
) -> AnalysisResult:
    # 0) Rate limit: reject (429) BEFORE spending a Gemini call if over quota.
    ip = client_ip(request)
    enforce_limits(db, ip)

    # 1) Ask Gemini for the structured analysis.
    result = analyze_listing(payload.text)

    # 2) Best-effort: add our own model's price prediction (None if untrained).
    listing = result.listing
    if all(v is not None for v in (listing.brand, listing.year, listing.km,
                                   listing.fuel_type, listing.transmission)):
        result.predicted_price = predict_price(
            brand=listing.brand,
            year=listing.year,
            km=listing.km,
            fuel_type=listing.fuel_type,
            transmission=listing.transmission,
        )

    # 3) Persist this analysis (flattened) for history + future ML training.
    record = AnalysisRecord(
        raw_text=payload.text,
        brand=listing.brand,
        model=listing.model,
        year=listing.year,
        km=listing.km,
        fuel_type=listing.fuel_type,
        transmission=listing.transmission,
        listed_price=listing.listed_price,
        verdict=result.verdict,
        opportunity_score=result.opportunity_score,
        market_low=result.market_low,
        market_high=result.market_high,
        price_diff=result.price_diff,
        pros=result.pros,
        cons=result.cons,
        negotiation_guide=result.negotiation_guide,
        expert_comment=result.expert_comment,
    )
    db.add(record)
    db.commit()

    # 4) Count this successful analysis against the caps.
    record_usage(db, ip)

    return result


@app.get("/api/usage", response_model=UsageStatus)
def usage(request: Request, db: Session = Depends(get_db)) -> UsageStatus:
    """How much quota this visitor has left today (drives the UI counter)."""
    return UsageStatus(**usage_status(db, client_ip(request)))


# ---------------------------------------------------------------------------
# HISTORY: list past analyses (newest first)
# ---------------------------------------------------------------------------
@app.get("/api/history", response_model=list[HistoryItem])
def history(limit: int = 50, db: Session = Depends(get_db)) -> list[AnalysisRecord]:
    return (
        db.query(AnalysisRecord)
        .order_by(AnalysisRecord.created_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/api/history/{item_id}", response_model=HistoryItem)
def history_item(item_id: int, db: Session = Depends(get_db)) -> AnalysisRecord:
    record = db.get(AnalysisRecord, item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return record


@app.delete("/api/history/{item_id}", status_code=204)
def delete_history_item(item_id: int, db: Session = Depends(get_db)) -> None:
    """Delete one past analysis. 204 = success with no body to return."""
    record = db.get(AnalysisRecord, item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    db.delete(record)
    db.commit()


# ---------------------------------------------------------------------------
# SCRAPE: fetch a listing URL -> raw text (convenience; paste is primary)
# ---------------------------------------------------------------------------
@app.post("/api/scrape", response_model=ScrapeResponse)
def scrape(request: ScrapeRequest) -> ScrapeResponse:
    try:
        text = scrape_listing(request.url)
    except ScrapeError as exc:
        # 422: we understood the request but couldn't fulfill it (blocked/empty).
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ScrapeResponse(text=text)


# ---------------------------------------------------------------------------
# PREDICT: our scikit-learn model's price estimate from a feature vector
# ---------------------------------------------------------------------------
@app.post("/api/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    price = predict_price(
        brand=request.brand,
        year=request.year,
        km=request.km,
        fuel_type=request.fuel_type,
        transmission=request.transmission,
    )
    if price is None:
        raise HTTPException(
            status_code=503,
            detail="No trained model available. Run: python ml.py train",
        )
    return PredictResponse(predicted_price=price)
