"""
analyzer.py — The ONLY file where the AI provider (Gemini) is ISOLATED.

WHY ISOLATE? (separation of concerns)
main.py only knows how to "handle HTTP traffic"; it does NOT know how Gemini is
called. If tomorrow we switch from Gemini to OpenAI, we change ONLY this file —
main.py / models.py stay untouched. The only contract main.py relies on is:
`analyze_listing(text) -> AnalysisResult`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from models import AnalysisResult

# ---------------------------------------------------------------------------
# Configuration / client setup
# ---------------------------------------------------------------------------
# Load the .env that sits next to this file (server/.env). We pass an explicit
# path because the server's working directory is the project root, not server/.
load_dotenv(Path(__file__).parent / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    # Fail fast with a clear message instead of a confusing error deep in a request.
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Copy server/.env.example to server/.env and fill it in."
    )

MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash"
]

# A single client is created once at import time and reused for every request.
client = genai.Client(api_key=API_KEY)

# ---------------------------------------------------------------------------
# System prompt — the "job description" we give the model on every call.
# ---------------------------------------------------------------------------
# Notice what is and is NOT here:
#  - It defines a ROLE, the TASKS, the SCORING rules, and language/anti-hallucination
#    constraints.
#  - It does NOT describe the JSON shape. We delegate the output structure to
#    `response_schema` below, so the model is freed to focus on REASONING quality
#    while the library guarantees a valid, schema-correct JSON object.
SYSTEM_PROMPT = """\
You are an expert used-car appraiser specializing in the Turkish second-hand
market (sahibinden.com). You are given the raw, messy text of a single car
listing and you produce a rigorous valuation.

Your tasks:
1. EXTRACT the structured facts: brand, model, year, km, fuel_type, transmission,
   listed_price (asking price), city (the city where the car is located),
   body_type (one of: Sedan, Hatchback, SUV, Pickup, Coupe, MPV, Station), and
   has_damage (true if the listing mentions any accident history, bodywork damage,
   or damage record — "hasar kayıtlı", "boyalı", "değişen" etc.; false otherwise).
   If a field is genuinely absent from the text, set it to null.
   NEVER invent values that are not supported by the text.
2. ESTIMATE a realistic market price RANGE in Turkish Lira (TRY) for this exact
   car, based on its segment, model year, mileage, and any condition signals.
   market_low and market_high bound a typical fair transaction price.
3. COMPUTE price_diff = listed_price minus the MIDPOINT of your market range.
   A negative price_diff means the listing is below market (a potential deal).
4. SCORE the opportunity from 0 to 100 (opportunity_score); higher = better buy.
   Weigh price vs. market, mileage, age, condition red flags, and demand.
5. Choose exactly ONE verdict label:
   - "DEAL"       when at or below fair value with acceptable risk (score >= 65)
   - "FAIR"       when priced about right (score 40-64)
   - "OVERPRICED" when above fair value or carrying high risk (score < 40)
6. List concrete pros and cons as short bullet strings.
7. Write a negotiation_guide: a practical strategy (opening offer, leverage
   points, a target price).
8. Write an expert_comment: a concise, professional overall assessment.
9. Using your vast automotive knowledge, identify the chronic issues (kronik sorunlar)
   known for this specific brand/model/engine/year combination. List them as strings in `chronic_issues`.
   If none are well-known, return an empty list or a generic note.
10. Write a `user_consensus`: a short summary of how users generally rate this specific vehicle (e.g. good handling, bad fuel economy, reliable).
Hard rules:
- Base everything ONLY on the provided text plus general market knowledge.
  Do not fabricate specific facts that the text does not imply.
- All human-readable content (pros, cons, negotiation_guide, expert_comment)
  MUST be written in TURKISH — the end users are Turkish car buyers.
- The verdict must be exactly one of the three English labels above.
- All monetary values are integers in TRY, with no thousands separators.
"""


def analyze_listing(text: str) -> AnalysisResult:
    """Send the raw listing text to Gemini and return a structured analysis.

    The magic is in `config`:
    - system_instruction  -> the role/rules above, separate from the user's text
    - response_mime_type   -> forces the model to answer in JSON (not prose)
    - response_schema      -> our Pydantic model; the library validates the JSON
                              against it AND hands us a ready-made AnalysisResult
    - temperature (low)    -> we want consistent, grounded valuations, not creativity
    """
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=AnalysisResult,
        temperature=0.3,
    )

    last_error = None
    for model_name in MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=text,
                config=config,
            )

            # When response_schema is a Pydantic model, the SDK parses the JSON for us.
            result = response.parsed
            if result is None:
                # Defensive fallback: parse the raw JSON text ourselves.
                result = AnalysisResult.model_validate_json(response.text)

            return result
        except Exception as e:
            print(f"[analyzer] Model {model_name} failed: {e}")
            last_error = e

    # If all models fail, raise the last error
    raise RuntimeError(f"All models failed due to rate limits or errors. Last error: {last_error}")
