"""
ml.py — Phase 4: a scikit-learn price-prediction model, ISOLATED here.

Pipeline overview:
    features (brand, year, km, fuel_type, transmission)  -->  target (price TRY)

We train a RandomForestRegressor wrapped in a scikit-learn Pipeline:
    ColumnTransformer
      - OneHotEncoder on categorical columns (brand, fuel_type, transmission)
      - passthrough on numeric columns (year, km)
    -> RandomForestRegressor

The model is persisted to model.joblib next to this file and lazily loaded at
predict time.

Why a synthetic bootstrap?  In the real product the model trains on the rows we
collect in SQLite over time. Early on we have almost no rows, and a model needs
LOTS of data. So when the DB has too few rows, we generate a realistic synthetic
Turkish used-car dataset to bootstrap a usable model. As real data accumulates,
retraining on it takes over. (This is also our teaching example for overfitting,
train/test split, and "why we need lots of data".)

CLI:
    python ml.py export   # dump the DB rows to a pandas DataFrame (preview)
    python ml.py train    # train the model and report train/test error
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from database import Base, SessionLocal, engine
from models import AnalysisRecord

MODEL_PATH = Path(__file__).parent / "model.joblib"

# The feature vector. CATEGORICAL = text buckets, NUMERIC = real numbers.
CATEGORICAL = ["brand", "fuel_type", "transmission"]
NUMERIC = ["year", "km"]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "listed_price"

# Below this many usable rows in the DB, we bootstrap with synthetic data.
MIN_REAL_ROWS = 50


# ---------------------------------------------------------------------------
# DATA EXPORT: SQLite -> pandas DataFrame  (Step 15)
# ---------------------------------------------------------------------------
def export_dataframe() -> pd.DataFrame:
    """Read every analysis row from SQLite into a pandas DataFrame.

    Only rows where all features and the target are present are useful for
    training, so we drop the rest.
    """
    # Ensure the table exists even when ml.py runs standalone (before the API
    # has ever booted and created it).
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        rows = db.query(AnalysisRecord).all()
        data = [
            {
                "brand": r.brand,
                "fuel_type": r.fuel_type,
                "transmission": r.transmission,
                "year": r.year,
                "km": r.km,
                "listed_price": r.listed_price,
            }
            for r in rows
        ]
    finally:
        db.close()

    df = pd.DataFrame(data, columns=FEATURES + [TARGET])
    df = df.dropna(subset=FEATURES + [TARGET])
    return df


# ---------------------------------------------------------------------------
# SYNTHETIC BOOTSTRAP DATA
# ---------------------------------------------------------------------------
# Rough 2024-era base prices (TRY) for a NEWEST-year, low-km example per brand.
_BRAND_BASE = {
    "Volkswagen": 1_300_000,
    "Renault": 950_000,
    "Fiat": 900_000,
    "Ford": 1_150_000,
    "Opel": 1_000_000,
    "Toyota": 1_400_000,
    "Honda": 1_300_000,
    "Hyundai": 1_100_000,
    "Peugeot": 980_000,
    "BMW": 2_300_000,
    "Mercedes-Benz": 2_500_000,
    "Audi": 2_200_000,
}
_FUELS = ["Benzin", "Dizel", "LPG & Benzin", "Hibrit"]
_TRANSMISSIONS = ["Manuel", "Otomatik"]


def _synthetic_dataframe(n: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Generate a realistic-ish synthetic dataset to bootstrap the model."""
    rng = np.random.default_rng(seed)
    brands = list(_BRAND_BASE.keys())
    current_year = 2024

    rows = []
    for _ in range(n):
        brand = rng.choice(brands)
        year = int(rng.integers(2008, current_year + 1))
        km = int(rng.integers(0, 320_000))
        fuel = rng.choice(_FUELS, p=[0.42, 0.40, 0.13, 0.05])
        trans = rng.choice(_TRANSMISSIONS, p=[0.45, 0.55])

        base = _BRAND_BASE[brand]
        age = current_year - year
        # ~5% depreciation per year (Turkish used cars hold value under inflation).
        price = base * (0.95 ** age)
        # Mileage penalty, capped so high-km cars don't collapse to nothing.
        price *= max(0.70, 1 - (km / 300_000) * 0.25)
        # Fuel / transmission adjustments.
        price *= {"Benzin": 1.0, "Dizel": 1.06, "LPG & Benzin": 0.93, "Hibrit": 1.18}[fuel]
        price *= 1.08 if trans == "Otomatik" else 1.0
        # Random market noise.
        price *= rng.normal(1.0, 0.07)

        rows.append(
            {
                "brand": brand,
                "fuel_type": fuel,
                "transmission": trans,
                "year": year,
                "km": km,
                "listed_price": int(max(120_000, price)),
            }
        )
    return pd.DataFrame(rows, columns=FEATURES + [TARGET])


# ---------------------------------------------------------------------------
# TRAINING  (Steps 16 & 19)
# ---------------------------------------------------------------------------
def _build_pipeline() -> Pipeline:
    """Categorical -> one-hot, numeric -> passthrough, then a RandomForest."""
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", "passthrough", NUMERIC),
        ]
    )
    model = RandomForestRegressor(n_estimators=200, max_depth=14, random_state=42)
    return Pipeline([("prep", pre), ("rf", model)])


def train(verbose: bool = True) -> Pipeline:
    """Train on real DB rows if we have enough, else on synthetic data.

    We hold out a TEST split so the reported error reflects unseen data, not
    rows the model already memorized (that gap is exactly overfitting).
    """
    import joblib

    df = export_dataframe()
    source = "database"
    if len(df) < MIN_REAL_ROWS:
        df = _synthetic_dataframe()
        source = "synthetic bootstrap"

    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipe = _build_pipeline()
    pipe.fit(X_train, y_train)

    joblib.dump(pipe, MODEL_PATH)

    if verbose:
        train_mae = mean_absolute_error(y_train, pipe.predict(X_train))
        test_mae = mean_absolute_error(y_test, pipe.predict(X_test))
        test_r2 = r2_score(y_test, pipe.predict(X_test))
        print(f"Trained on {len(df)} rows ({source}).")
        print(f"  Train MAE: {train_mae:,.0f} TRY")
        print(f"  Test  MAE: {test_mae:,.0f} TRY   (gap vs train ~ overfitting)")
        print(f"  Test  R^2: {test_r2:.3f}")
        print(f"Saved model -> {MODEL_PATH}")

    return pipe


# ---------------------------------------------------------------------------
# PREDICTION (used by /api/predict and /api/analyze)
# ---------------------------------------------------------------------------
_cached_model: Pipeline | None = None


def _load_model() -> Pipeline | None:
    """Lazily load model.joblib from disk, caching it in memory."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    if not MODEL_PATH.exists():
        return None
    import joblib

    _cached_model = joblib.load(MODEL_PATH)
    return _cached_model


def predict_price(
    brand: str, year: int, km: int, fuel_type: str, transmission: str
) -> int | None:
    """Predict a price from a feature vector. Returns None if no model exists yet."""
    model = _load_model()
    if model is None:
        return None

    X = pd.DataFrame(
        [
            {
                "brand": brand,
                "fuel_type": fuel_type,
                "transmission": transmission,
                "year": year,
                "km": km,
            }
        ],
        columns=FEATURES,
    )
    pred = model.predict(X)[0]
    return int(round(pred))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "export":
        frame = export_dataframe()
        print(f"{len(frame)} usable rows in the database:")
        print(frame.head(20).to_string())
    elif cmd == "train":
        train()
    else:
        print("Usage: python ml.py [train|export]")
