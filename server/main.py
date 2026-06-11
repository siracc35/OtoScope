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

import os
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from analyzer import analyze_listing
from database import Base, engine, get_db
from ml import get_model_info, predict_price
from models import (
    AnalysisRecord,
    AnalysisResult,
    AnalyzeRequest,
    BatchRequest,
    BatchResultItem,
    HistoryItem,
    ListingData,
    ModelInfo,
    PredictRequest,
    PredictResponse,
    ScrapeRequest,
    ScrapeResponse,
    TrendPoint,
    TrendSeries,
    UsageStatus,
    WatchlistAddRequest,
    WatchlistItem,
    WatchlistRecord,
)
from ratelimit import client_ip, enforce_limits, record_usage, usage_status
from scraper import ScrapeError, scrape_listing

# Create all tables on startup if they don't exist yet.
Base.metadata.create_all(bind=engine)

with engine.begin() as conn:
    for stmt in [
        "ALTER TABLE analyses ADD COLUMN chronic_issues JSON NOT NULL DEFAULT '[]'",
        "ALTER TABLE analyses ADD COLUMN user_consensus TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE analyses ADD COLUMN city TEXT",
        "ALTER TABLE analyses ADD COLUMN body_type TEXT",
        "ALTER TABLE analyses ADD COLUMN has_damage BOOLEAN",
    ]:
        try:
            conn.execute(text(stmt))
        except Exception:
            pass

app = FastAPI(title="OtoScope API", version="1.0.0")


def compute_opportunity_score(result: AnalysisResult) -> int:
    """
    Gemini'nin sabit değer üretme sorununu bypass etmek için skoru
    analiz sonuçlarından server-side hesapla.
    """
    from datetime import datetime
    score = 55

    # Fiyat pozisyonu — Türkiye piyasasında satıcılar genelde %5-10 üstünde açar,
    # bu normal; %20+ pahalı ya da %10+ ucuz gerçek bir sinyal.
    # ±30 puanlık bant, %30'da platoya ulaşır.
    market_mid = (result.market_low + result.market_high) / 2 if result.market_low and result.market_high else None
    if market_mid and market_mid > 0 and result.listing.listed_price:
        pct = max(-0.30, min(0.30, result.price_diff / market_mid))
        score -= int(pct * 60)

    # Hasar kaydı — ciddi risk
    if result.listing.has_damage:
        score -= 18

    # Kilometre cezası
    km = result.listing.km or 0
    if km > 300_000:
        score -= 15
    elif km > 200_000:
        score -= 8
    elif km > 150_000:
        score -= 4

    # Yaş cezası
    year = result.listing.year
    if year:
        age = datetime.now().year - year
        if age > 20:
            score -= 8
        elif age > 15:
            score -= 4

    # Pros/cons dengesi — Gemini 3-4 madde verir, net fark önemli sinyal
    pros_count = len(result.pros or [])
    cons_count = len(result.cons or [])
    score += (pros_count - cons_count) * 5

    # Kronik sorun sayısı
    score -= len(result.chronic_issues or []) * 2

    return max(0, min(100, score))

_retrain_lock = threading.Lock()

def _background_retrain(row_count: int) -> None:
    """Retrain the ML model in a background thread after every 5 new analyses.
    Always combines DB rows with arabam.com scraped data for maximum coverage.
    """
    if row_count % 5 != 0:
        return
    if not _retrain_lock.acquire(blocking=False):
        return  # already retraining
    def _run():
        try:
            from ml import train
            print(f"[ml] Auto-retrain triggered at {row_count} DB rows…")
            train(verbose=True)
            print("[ml] Auto-retrain complete.")
        except Exception as e:
            print(f"[ml] Auto-retrain failed: {e}")
        finally:
            _retrain_lock.release()
    threading.Thread(target=_run, daemon=True).start()

# CORS: production'da ALLOWED_ORIGINS env var'ı ile kısıtla.
# Varsayılan "*" — geliştirme ve Railway single-service için uygundur.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_allow_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
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
    result.opportunity_score = compute_opportunity_score(result)

    # 2) Best-effort: add our own model's price prediction (None if untrained).
    listing = result.listing
    if all(v is not None for v in (listing.brand, listing.year, listing.km,
                                   listing.fuel_type, listing.transmission)):
        result.predicted_price = predict_price(
            brand=listing.brand,
            model=listing.model,
            year=listing.year,
            km=listing.km,
            fuel_type=listing.fuel_type,
            transmission=listing.transmission,
            city=listing.city,
            body_type=listing.body_type,
            has_damage=listing.has_damage,
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
        city=listing.city,
        body_type=listing.body_type,
        has_damage=listing.has_damage,
        verdict=result.verdict,
        opportunity_score=result.opportunity_score,
        market_low=result.market_low,
        market_high=result.market_high,
        price_diff=result.price_diff,
        pros=result.pros,
        cons=result.cons,
        negotiation_guide=result.negotiation_guide,
        expert_comment=result.expert_comment,
        chronic_issues=result.chronic_issues,
        user_consensus=result.user_consensus,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    result.id = record.id

    # 4) Count this successful analysis against the caps.
    record_usage(db, ip)

    # 5) Trigger background retrain when enough real data has accumulated.
    row_count = db.query(AnalysisRecord).count()
    _background_retrain(row_count)

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


@app.get("/api/history/{item_id}", response_model=AnalysisResult)
def history_item(item_id: int, db: Session = Depends(get_db)) -> AnalysisResult:
    record = db.get(AnalysisRecord, item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    predicted_price = None
    if all(v is not None for v in (record.brand, record.year, record.km,
                                   record.fuel_type, record.transmission)):
        predicted_price = predict_price(
            brand=record.brand,
            model=record.model,
            year=record.year,
            km=record.km,
            fuel_type=record.fuel_type,
            transmission=record.transmission,
            city=record.city,
            body_type=record.body_type,
            has_damage=record.has_damage,
        )

    return AnalysisResult(
        id=record.id,
        verdict=record.verdict,
        opportunity_score=record.opportunity_score,
        market_low=record.market_low,
        market_high=record.market_high,
        price_diff=record.price_diff,
        pros=record.pros,
        cons=record.cons,
        negotiation_guide=record.negotiation_guide,
        expert_comment=record.expert_comment,
        chronic_issues=record.chronic_issues or [],
        user_consensus=record.user_consensus or "",
        predicted_price=predicted_price,
        listing=ListingData(
            brand=record.brand,
            model=record.model,
            year=record.year,
            km=record.km,
            fuel_type=record.fuel_type,
            transmission=record.transmission,
            listed_price=record.listed_price,
            city=record.city,
            body_type=record.body_type,
            has_damage=record.has_damage,
        ),
    )


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


# ---------------------------------------------------------------------------
# TRENDS: price history aggregated by brand/month
# ---------------------------------------------------------------------------
@app.get("/api/trends", response_model=list[TrendSeries])
def trends(brand: str | None = None, db: Session = Depends(get_db)) -> list[TrendSeries]:
    from sqlalchemy import func as sqlfunc, text as sqltext

    query = db.query(
        AnalysisRecord.brand,
        AnalysisRecord.model,
        sqlfunc.strftime("%Y-%m", AnalysisRecord.created_at).label("month"),
        sqlfunc.avg(AnalysisRecord.listed_price).label("avg_price"),
        sqlfunc.count(AnalysisRecord.id).label("count"),
    ).filter(
        AnalysisRecord.listed_price.isnot(None),
        AnalysisRecord.brand.isnot(None),
    )

    if brand:
        query = query.filter(AnalysisRecord.brand == brand)

    rows = (
        query.group_by(AnalysisRecord.brand, AnalysisRecord.model, "month")
        .order_by("month")
        .all()
    )

    # Group into series keyed by (brand, model)
    series_map: dict[tuple, list[TrendPoint]] = {}
    for row in rows:
        key = (row.brand, row.model)
        series_map.setdefault(key, []).append(
            TrendPoint(month=row.month, avg_price=int(row.avg_price), count=row.count)
        )

    return [
        TrendSeries(brand=brand_name, model=model_name, points=pts)
        for (brand_name, model_name), pts in series_map.items()
    ]


@app.get("/api/trends/brands", response_model=list[str])
def trend_brands(db: Session = Depends(get_db)) -> list[str]:
    """Return distinct brands that have at least one analysis with a price."""
    rows = (
        db.query(AnalysisRecord.brand)
        .filter(AnalysisRecord.brand.isnot(None), AnalysisRecord.listed_price.isnot(None))
        .distinct()
        .order_by(AnalysisRecord.brand)
        .all()
    )
    return [r.brand for r in rows]


# ---------------------------------------------------------------------------
# WATCHLIST: save/unsave analyses
# ---------------------------------------------------------------------------
@app.get("/api/watchlist", response_model=list[WatchlistItem])
def get_watchlist(db: Session = Depends(get_db)) -> list[WatchlistRecord]:
    return db.query(WatchlistRecord).order_by(WatchlistRecord.created_at.desc()).all()


@app.post("/api/watchlist", response_model=WatchlistItem, status_code=201)
def add_watchlist(req: WatchlistAddRequest, db: Session = Depends(get_db)) -> WatchlistRecord:
    if db.get(AnalysisRecord, req.analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    existing = (
        db.query(WatchlistRecord)
        .filter(WatchlistRecord.analysis_id == req.analysis_id)
        .first()
    )
    if existing:
        return existing
    record = WatchlistRecord(analysis_id=req.analysis_id, note=req.note)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.delete("/api/watchlist/{item_id}", status_code=204)
def remove_watchlist(item_id: int, db: Session = Depends(get_db)) -> None:
    record = db.get(WatchlistRecord, item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(record)
    db.commit()


@app.delete("/api/watchlist/by-analysis/{analysis_id}", status_code=204)
def remove_watchlist_by_analysis(analysis_id: int, db: Session = Depends(get_db)) -> None:
    record = (
        db.query(WatchlistRecord)
        .filter(WatchlistRecord.analysis_id == analysis_id)
        .first()
    )
    if record:
        db.delete(record)
        db.commit()


# ---------------------------------------------------------------------------
# MODEL INFO: ML training metadata
# ---------------------------------------------------------------------------
@app.get("/api/model/info", response_model=ModelInfo)
def model_info() -> ModelInfo:
    return ModelInfo(**get_model_info())


# ---------------------------------------------------------------------------
# BATCH ANALYSIS: analyze multiple listings in one call (max 10)
# ---------------------------------------------------------------------------
@app.post("/api/batch", response_model=list[BatchResultItem])
def batch_analyze(
    payload: BatchRequest, request: Request, db: Session = Depends(get_db)
) -> list[BatchResultItem]:
    ip = client_ip(request)
    results: list[BatchResultItem] = []

    for i, text in enumerate(payload.texts):
        try:
            enforce_limits(db, ip)
            result = analyze_listing(text)
            result.opportunity_score = compute_opportunity_score(result)
            listing = result.listing
            if all(v is not None for v in (listing.brand, listing.year, listing.km,
                                           listing.fuel_type, listing.transmission)):
                result.predicted_price = predict_price(
                    brand=listing.brand, model=listing.model, year=listing.year,
                    km=listing.km, fuel_type=listing.fuel_type,
                    transmission=listing.transmission, city=listing.city,
                    body_type=listing.body_type, has_damage=listing.has_damage,
                )
            record = AnalysisRecord(
                raw_text=text, brand=listing.brand, model=listing.model,
                year=listing.year, km=listing.km, fuel_type=listing.fuel_type,
                transmission=listing.transmission, listed_price=listing.listed_price,
                city=listing.city, body_type=listing.body_type, has_damage=listing.has_damage,
                verdict=result.verdict, opportunity_score=result.opportunity_score,
                market_low=result.market_low, market_high=result.market_high,
                price_diff=result.price_diff, pros=result.pros, cons=result.cons,
                negotiation_guide=result.negotiation_guide,
                expert_comment=result.expert_comment,
                chronic_issues=result.chronic_issues,
                user_consensus=result.user_consensus,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            result.id = record.id
            record_usage(db, ip)
            results.append(BatchResultItem(index=i, success=True, result=result))
        except HTTPException as exc:
            results.append(BatchResultItem(index=i, success=False, error=exc.detail))
            if exc.status_code == 429:
                # Quota exhausted — no point trying the rest.
                for j in range(i + 1, len(payload.texts)):
                    results.append(BatchResultItem(index=j, success=False, error="Günlük kota aşıldı"))
                break
        except Exception as exc:
            results.append(BatchResultItem(index=i, success=False, error=str(exc)))

    return results


# ---------------------------------------------------------------------------
# FRONTEND — tek servis deploy için Vite build'ini sun
# ---------------------------------------------------------------------------
_DIST = Path(__file__).parent.parent / "client" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
