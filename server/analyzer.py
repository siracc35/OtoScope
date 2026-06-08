"""
analyzer.py — The ONLY file where the AI provider (Gemini) is ISOLATED.

WHY ISOLATE? (separation of concerns)
main.py only knows how to "handle HTTP traffic"; it does NOT know how Gemini is
called. If tomorrow we switch from Gemini to OpenAI, we change ONLY this file —
main.py / models.py stay untouched. The only thing main.py cares about is that
this module exposes `analyze_listing(text) -> AnalysisResult`.

RIGHT NOW: Gemini is not wired in yet. We return a fixed (mock) result so we can
test the HTTP pipeline INDEPENDENTLY of Gemini. In Step 3 the BODY of this
function changes; its SIGNATURE (parameters and return type) stays the same.
"""

from models import AnalysisResult, ListingData


def analyze_listing(text: str) -> AnalysisResult:
    """Take raw listing text, return a structured analysis.

    For now we ignore 'text' and produce a fixed sample.
    In Step 3 we will call the Gemini API here.
    """

    return AnalysisResult(
        listing=ListingData(
            brand="Volkswagen",
            model="Passat 1.6 TDI",
            year=2016,
            km=185000,
            fuel_type="Diesel",
            transmission="Automatic",
            listed_price=985000,
        ),
        verdict="DEAL",
        opportunity_score=78,
        market_low=950000,
        market_high=1150000,
        price_diff=-65000,  # listed price is 65k below the market midpoint
        pros=[
            "Price is below market average",
            "Well-maintained diesel engine, fuel efficient",
        ],
        cons=[
            "High mileage (185,000 km)",
            "DSG gearbox service history should be checked",
        ],
        negotiation_guide=(
            "Use the high mileage as leverage. Open at 950,000 TRY, "
            "request DSG service invoices; if missing, target 920,000."
        ),
        expert_comment=(
            "With a clean service history this price sits in the fair-to-good range. "
            "A confirmed DSG and timing belt/chain status makes it a deal."
        ),
    )
