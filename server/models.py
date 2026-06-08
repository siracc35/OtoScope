"""
models.py — Defines the SHAPE of our data.

For now this file only holds Pydantic models (the API's input/output contract).
In Phase 1 / Step 4 we will add SQLAlchemy models (the DB table) here as well.

KEY DISTINCTION (we will go deeper later):
- Pydantic model   -> "Is the incoming/outgoing data well-formed?" (API contract)
- SQLAlchemy model -> "Which table and columns does this data live in?" (persistence)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


# ===========================================================================
# SQLALCHEMY MODEL (persistence) — "how the data lives in the DB"
# ===========================================================================
class AnalysisRecord(Base):
    """One row per analysis in the 'analyses' table.

    Note it is FLAT: listing fields (brand, year, km, ...) become their own
    columns instead of a nested object. This makes them easy to query and to
    feed into our future ML model. pros/cons are lists, so we store them in
    JSON columns (SQLite keeps JSON as text under the hood).
    """

    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    # server_default=func.now() -> the DB stamps the time on insert, not Python.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raw_text = Column(Text, nullable=False)  # the original pasted listing

    # --- extracted listing facts (flattened) ---
    brand = Column(String, nullable=True)
    model = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    km = Column(Integer, nullable=True)
    fuel_type = Column(String, nullable=True)
    transmission = Column(String, nullable=True)
    listed_price = Column(Integer, nullable=True)
    city = Column(String, nullable=True)
    body_type = Column(String, nullable=True)
    has_damage = Column(Boolean, nullable=True)

    # --- analysis results ---
    verdict = Column(String, nullable=False)
    opportunity_score = Column(Integer, nullable=False)
    market_low = Column(Integer, nullable=False)
    market_high = Column(Integer, nullable=False)
    price_diff = Column(Integer, nullable=False)
    pros = Column(JSON, nullable=False)
    cons = Column(JSON, nullable=False)
    negotiation_guide = Column(Text, nullable=False)
    expert_comment = Column(Text, nullable=False)
    chronic_issues = Column(JSON, nullable=False)
    user_consensus = Column(Text, nullable=False)

class UsageRecord(Base):
    """One row per (ip, day) — how many analyses that IP ran on that calendar day.

    This is our lightweight rate-limit ledger. We sum it for the global cap and
    read a single row for the per-IP cap. (day is stored as 'YYYY-MM-DD' text.)
    """

    __tablename__ = "usage"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, index=True)
    day = Column(String, nullable=False, index=True)
    count = Column(Integer, nullable=False, default=0)


# ===========================================================================
# PYDANTIC MODELS (API contract) — "is the data well-formed at the HTTP edge"
# ===========================================================================

# ---------------------------------------------------------------------------
# REQUEST model
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    """The raw listing text pasted by the user.

    When FastAPI sees this model it AUTOMATICALLY validates the incoming JSON:
    - missing 'text'      -> 422 error (without us writing code)
    - 'text' not a string -> 422 error
    min_length=1 also rejects empty strings.
    """

    text: str = Field(..., min_length=1, description="Raw text of a sahibinden.com listing page")


# ---------------------------------------------------------------------------
# RESPONSE models
# ---------------------------------------------------------------------------
class ListingData(BaseModel):
    """Structured car data EXTRACTED from the listing (Gemini pulls these from text)."""

    brand: str | None = Field(None, description="Brand, e.g. Volkswagen")
    model: str | None = Field(None, description="Model, e.g. Passat 1.6 TDI")
    year: int | None = Field(None, description="Model year")
    km: int | None = Field(None, description="Mileage in kilometers")
    fuel_type: str | None = Field(None, description="Fuel type, e.g. Diesel")
    transmission: str | None = Field(None, description="Transmission, e.g. Automatic")
    listed_price: int | None = Field(None, description="Asking price in the listing (TRY)")
    city: str | None = Field(None, description="City where the car is listed, e.g. İstanbul")
    body_type: str | None = Field(None, description="Body type: Sedan, Hatchback, SUV, Pickup, Coupe, MPV, Station")
    has_damage: bool | None = Field(None, description="True if the listing mentions any accident/damage record")



class AnalysisResult(BaseModel):
    """The full analysis returned by the endpoint. Every dashboard box reads from here."""

    listing: ListingData

    verdict: str = Field(..., description="Short verdict label: DEAL | FAIR | OVERPRICED")
    opportunity_score: int = Field(..., ge=0, le=100, description="Opportunity score 0-100")

    market_low: int = Field(..., description="Estimated market floor (TRY)")
    market_high: int = Field(..., description="Estimated market ceiling (TRY)")
    price_diff: int = Field(
        ...,
        description="Listed price - market midpoint. Negative = below market (good).",
    )

    pros: list[str] = Field(default_factory=list, description="Positive signals")
    cons: list[str] = Field(default_factory=list, description="Negatives / risks")

    negotiation_guide: str = Field(..., description="Negotiation strategy text")
    expert_comment: str = Field(..., description="Expert commentary / overall assessment")
    chronic_issues: list[str] = Field(default_factory=list, description="List of chronic issues known for this car model")
    user_consensus: str = Field("", description="General consensus and user experiences with this vehicle")

    id: int | None = Field(None, description="Database ID of this saved analysis")

    # Filled by our own ML model (Phase 4) when a trained model is available.
    # Optional: stays None if no model has been trained yet.
    predicted_price: int | None = Field(
        None, description="Price predicted by our scikit-learn model (TRY)"
    )


# ---------------------------------------------------------------------------
# HISTORY model — serializes an ORM row (AnalysisRecord) back out as JSON
# ---------------------------------------------------------------------------
class HistoryItem(BaseModel):
    """A past analysis returned by /api/history.

    model_config = from_attributes lets Pydantic read directly from a
    SQLAlchemy ORM object's attributes (record.brand, record.verdict, ...),
    so we can do HistoryItem.model_validate(record) without manual mapping.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    brand: str | None
    model: str | None
    year: int | None
    km: int | None
    fuel_type: str | None
    transmission: str | None
    listed_price: int | None
    city: str | None
    body_type: str | None
    has_damage: bool | None
    verdict: str
    opportunity_score: int
    market_low: int
    market_high: int
    price_diff: int
    pros: list[str]
    cons: list[str]
    negotiation_guide: str
    expert_comment: str
    chronic_issues: list[str]
    user_consensus: str


# ---------------------------------------------------------------------------
# SCRAPING models (Phase 3)
# ---------------------------------------------------------------------------
class ScrapeRequest(BaseModel):
    url: str = Field(..., description="A sahibinden.com listing URL")


class ScrapeResponse(BaseModel):
    text: str = Field(..., description="Extracted listing text, ready to analyze")


# ---------------------------------------------------------------------------
# ML PREDICTION models (Phase 4)
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    """The feature vector our model needs to predict a price."""

    brand: str
    model: str | None = None
    year: int
    km: int
    fuel_type: str
    transmission: str
    city: str | None = None
    body_type: str | None = None
    has_damage: bool | None = None


class PredictResponse(BaseModel):
    predicted_price: int = Field(..., description="Model-predicted price (TRY)")


# ---------------------------------------------------------------------------
# RATE-LIMIT status (shown in the UI so users see their remaining quota)
# ---------------------------------------------------------------------------
class UsageStatus(BaseModel):
    used: int = Field(..., description="Analyses this IP ran today")
    limit: int = Field(..., description="Per-IP daily cap")
    remaining: int = Field(..., description="Per-IP analyses left today")
    global_used: int = Field(..., description="Analyses all users ran today")
    global_limit: int = Field(..., description="Global daily cap")
    exempt: bool = Field(False, description="True if this caller bypasses the limits")


# ===========================================================================
# WATCHLIST — saved/favourite analyses
# ===========================================================================
class WatchlistRecord(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, nullable=False, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WatchlistItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    note: str | None
    created_at: datetime


class WatchlistAddRequest(BaseModel):
    analysis_id: int
    note: str | None = None


# ===========================================================================
# TRENDS — price history aggregation
# ===========================================================================
class TrendPoint(BaseModel):
    month: str
    avg_price: int
    count: int


class TrendSeries(BaseModel):
    brand: str
    model: str | None
    points: list[TrendPoint]


# ===========================================================================
# ML MODEL INFO — training metadata
# ===========================================================================
class ModelInfo(BaseModel):
    trained: bool
    row_count: int | None = None
    train_mae: float | None = None
    test_mae: float | None = None
    test_r2: float | None = None
    source: str | None = None
    trained_at: str | None = None


# ===========================================================================
# BATCH ANALYSIS
# ===========================================================================
class BatchRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=10)


class BatchResultItem(BaseModel):
    index: int
    success: bool
    result: AnalysisResult | None = None
    error: str | None = None
