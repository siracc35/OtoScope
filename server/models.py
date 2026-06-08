"""
models.py — Defines the SHAPE of our data.

For now this file only holds Pydantic models (the API's input/output contract).
In Phase 1 / Step 4 we will add SQLAlchemy models (the DB table) here as well.

KEY DISTINCTION (we will go deeper later):
- Pydantic model   -> "Is the incoming/outgoing data well-formed?" (API contract)
- SQLAlchemy model -> "Which table and columns does this data live in?" (persistence)
"""

from pydantic import BaseModel, Field


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
