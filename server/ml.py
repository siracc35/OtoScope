"""
ml.py — scikit-learn price-prediction model.

Feature set (expanded):
    brand, model, year, km, fuel_type, transmission,
    city, body_type, has_damage  -->  target: listed_price (TRY)

Algorithm: HistGradientBoostingRegressor
  - Handles high-cardinality categoricals (model names) via OrdinalEncoder
  - Natively tolerates NaN/None in numeric columns — no imputation needed
  - Faster and more accurate than RandomForest on tabular data at this scale

The model is persisted to model.joblib and lazily loaded at predict time.
When the DB has too few rows we scrape arabam.com; if that also fails we fall
back to a synthetic bootstrap.

CLI:
    python ml.py export   # dump DB rows to stdout
    python ml.py train    # train and report error metrics
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from database import Base, SessionLocal, engine
from models import AnalysisRecord
from scraper_arabam import scrape_arabam_listings

MODEL_PATH = Path(__file__).parent / "model.joblib"
MODEL_META_PATH = Path(__file__).parent / "model_meta.json"

CATEGORICAL = ["brand", "model", "fuel_type", "transmission", "city", "body_type"]
NUMERIC = ["year", "km", "has_damage"]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "listed_price"

MIN_REAL_ROWS = 50


# ---------------------------------------------------------------------------
# DATA EXPORT
# ---------------------------------------------------------------------------
def export_dataframe() -> pd.DataFrame:
    Base.metadata.create_all(bind=engine)
    # Ensure new columns exist (idempotent — fails silently if already present)
    from sqlalchemy import text as _text
    with engine.begin() as _conn:
        for _stmt in [
            "ALTER TABLE analyses ADD COLUMN chronic_issues JSON NOT NULL DEFAULT '[]'",
            "ALTER TABLE analyses ADD COLUMN user_consensus TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE analyses ADD COLUMN city TEXT",
            "ALTER TABLE analyses ADD COLUMN body_type TEXT",
            "ALTER TABLE analyses ADD COLUMN has_damage BOOLEAN",
        ]:
            try:
                _conn.execute(_text(_stmt))
            except Exception:
                pass
    db = SessionLocal()
    try:
        rows = db.query(AnalysisRecord).all()
        data = [
            {
                "brand":        r.brand,
                "model":        r.model,
                "fuel_type":    r.fuel_type,
                "transmission": r.transmission,
                "city":         r.city,
                "body_type":    r.body_type,
                "year":         r.year,
                "km":           r.km,
                "has_damage":   int(r.has_damage) if r.has_damage is not None else 0,
                "listed_price": r.listed_price,
            }
            for r in rows
        ]
    finally:
        db.close()

    df = pd.DataFrame(data, columns=FEATURES + [TARGET])
    # Only require the core fields; new optional columns can be NaN
    df = df.dropna(subset=["brand", "year", "km", TARGET])
    return df


# ---------------------------------------------------------------------------
# SYNTHETIC BOOTSTRAP
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TRAINING
# ---------------------------------------------------------------------------
def _build_pipeline() -> Pipeline:
    """OrdinalEncoder for categoricals + HistGradientBoostingRegressor.

    HistGBR advantages over RandomForest:
    - Handles NaN natively in numeric columns (no imputer needed)
    - Better accuracy on tabular data with mixed types
    - OrdinalEncoder + HistGBR is the recommended combo for high-cardinality
      categoricals (e.g. hundreds of distinct model names)

    Categorical NaN strategy: fill with "unknown" before OrdinalEncoder so the
    encoder always receives a valid string. Rows where city/body_type were not
    scraped simply become their own "unknown" bucket.
    """
    cat_pipeline = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("encode", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ])
    pre = ColumnTransformer(
        transformers=[
            ("cat", cat_pipeline, CATEGORICAL),
            ("num", "passthrough", NUMERIC),
        ]
    )
    hgb = HistGradientBoostingRegressor(
        max_iter=400,
        max_depth=8,
        learning_rate=0.05,
        min_samples_leaf=20,
        random_state=42,
    )
    return Pipeline([("prep", pre), ("hgb", hgb)])


def train(verbose: bool = True) -> Pipeline:
    import joblib

    df = export_dataframe()
    source = "database"

    if len(df) < MIN_REAL_ROWS:
        print("Not enough DB rows. Scraping arabam.com for training data…")
        scraped_data = scrape_arabam_listings()
        df_scraped = pd.DataFrame(scraped_data)
        df = pd.concat([df, df_scraped], ignore_index=True)
        df = df.dropna(subset=["brand", "year", "km", TARGET])
        source = "arabam.com + database"

    if len(df) < 5:
        raise RuntimeError(
            "Yeterli eğitim verisi yok. Önce birkaç ilan analiz edin veya "
            "arabam.com scraper'ının çalıştığından emin olun."
        )

    # Remove clearly bogus prices caused by scraper parsing errors.
    # Turkish used car market: realistic range is 50K – 20M TRY.
    before = len(df)
    df = df[(df[TARGET] >= 50_000) & (df[TARGET] <= 20_000_000)]
    removed = before - len(df)
    if removed:
        print(f"Removed {removed} rows with out-of-range prices.")

    # Fill optional columns that may be absent in older DB rows
    for col in ["model", "city", "body_type"]:
        if col not in df.columns:
            df[col] = None
    if "has_damage" not in df.columns:
        df["has_damage"] = 0
    else:
        df["has_damage"] = df["has_damage"].fillna(0).astype(int)

    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipe = _build_pipeline()
    pipe.fit(X_train, y_train)

    joblib.dump(pipe, MODEL_PATH)

    train_mae = mean_absolute_error(y_train, pipe.predict(X_train))
    test_mae  = mean_absolute_error(y_test,  pipe.predict(X_test))
    test_r2   = r2_score(y_test, pipe.predict(X_test))

    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "row_count":  len(df),
        "source":     source,
        "train_mae":  round(float(train_mae), 2),
        "test_mae":   round(float(test_mae), 2),
        "test_r2":    round(float(test_r2), 4),
    }
    MODEL_META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if verbose:
        print(f"Trained on {len(df)} rows ({source}).")
        print(f"  Train MAE: {train_mae:,.0f} TRY")
        print(f"  Test  MAE: {test_mae:,.0f} TRY")
        print(f"  Test  R²:  {test_r2:.3f}")
        print(f"Saved model -> {MODEL_PATH}")

    return pipe


# ---------------------------------------------------------------------------
# PREDICTION
# ---------------------------------------------------------------------------
_cached_model: Pipeline | None = None


def _load_model() -> Pipeline | None:
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    if not MODEL_PATH.exists():
        return None
    import joblib
    _cached_model = joblib.load(MODEL_PATH)
    return _cached_model


def predict_price(
    brand: str,
    year: int,
    km: int,
    fuel_type: str,
    transmission: str,
    model: str | None = None,
    city: str | None = None,
    body_type: str | None = None,
    has_damage: bool | None = None,
) -> int | None:
    pipe = _load_model()
    if pipe is None:
        return None

    X = pd.DataFrame(
        [{
            "brand":        brand,
            "model":        model,
            "fuel_type":    fuel_type,
            "transmission": transmission,
            "city":         city,
            "body_type":    body_type,
            "year":         year,
            "km":           km,
            "has_damage":   int(has_damage) if has_damage is not None else 0,
        }],
        columns=FEATURES,
    )
    pred = pipe.predict(X)[0]
    return int(round(pred))


# ---------------------------------------------------------------------------
# MODEL METADATA
# ---------------------------------------------------------------------------
def get_model_info() -> dict:
    if not MODEL_PATH.exists():
        return {"trained": False}
    meta = {"trained": True}
    if MODEL_META_PATH.exists():
        try:
            meta.update(json.loads(MODEL_META_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return meta


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
