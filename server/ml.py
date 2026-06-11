"""
ml.py — scikit-learn price-prediction model.

Feature set (expanded):
    brand, model, year, km, fuel_type, transmission,
    city, body_type, has_damage  -->  target: listed_price (TRY)

Engineered features (added at training/prediction time):
    age, km_per_year, age_squared

Algorithm: LGBMRegressor
  - Handles high-cardinality categoricals (model names) via OrdinalEncoder
  - Natively tolerates NaN/None in numeric columns — no imputation needed
  - Faster and more accurate than RandomForest on tabular data at this scale

The model is persisted to model.joblib and lazily loaded at predict time.
When the DB has too few rows we scrape arabam.com; if that also fails we fall
back to a synthetic bootstrap.

CLI:
    python ml.py export   # dump DB rows to stdout
    python ml.py train    # train and report error metrics
    python ml.py optimize # hyperparameter search via Optuna
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from lightgbm import LGBMRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from database import Base, SessionLocal, engine
from models import AnalysisRecord
from scraper_arabam import scrape_arabam_listings
from scraper_fordikinciel import scrape_fordikinciel_listings
from scraper_otosor import scrape_otosor_listings
from scraper_araba import scrape_araba_listings
from scraper_otoplus import scrape_otoplus_listings
from scraper_otoshops import scrape_otoshops_listings

try:
    from scraper_sahibinden import scrape_sahibinden_listings
    _SAHIBINDEN_AVAILABLE = True
except Exception:
    _SAHIBINDEN_AVAILABLE = False

MODEL_PATH = Path(__file__).parent / "model.joblib"
MODEL_META_PATH = Path(__file__).parent / "model_meta.json"

CATEGORICAL = ["brand", "model", "fuel_type", "transmission", "city", "body_type"]
NUMERIC = ["year", "km", "has_damage", "age", "km_per_year", "age_squared", "log_km", "log_age_plus1",
           "brand_median_price", "model_median_price"]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "listed_price"
LOG_TARGET = "log_price"

# Canonical brand name mapping — catches common scraper variations
BRAND_ALIASES: dict[str, str] = {
    "vw": "Volkswagen", "volkswagen": "Volkswagen",
    "mercedes": "Mercedes-Benz", "mercedes benz": "Mercedes-Benz",
    "bmw": "BMW",
    "renault": "Renault", "reno": "Renault",
    "peugeot": "Peugeot", "peugot": "Peugeot",
    "citroen": "Citroën", "citroën": "Citroën",
    "opel": "Opel",
    "fiat": "Fiat",
    "ford": "Ford",
    "toyota": "Toyota",
    "honda": "Honda",
    "hyundai": "Hyundai",
    "kia": "Kia",
    "nissan": "Nissan",
    "skoda": "Škoda", "škoda": "Škoda",
    "seat": "SEAT",
    "audi": "Audi",
    "volvo": "Volvo",
    "dacia": "Dacia",
    "mitsubishi": "Mitsubishi",
    "suzuki": "Suzuki",
    "mazda": "Mazda",
    "subaru": "Subaru",
    "jeep": "Jeep",
    "land rover": "Land Rover",
    "landrover": "Land Rover",
    "alfa romeo": "Alfa Romeo",
    "porsche": "Porsche",
    "lexus": "Lexus",
    "infiniti": "Infiniti",
    "mini": "MINI",
}

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
# FEATURE ENGINEERING
# ---------------------------------------------------------------------------
def normalize_brands(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize brand names using alias map."""
    df = df.copy()
    df["brand"] = df["brand"].apply(
        lambda b: BRAND_ALIASES.get(str(b).lower().strip(), str(b).strip()) if pd.notna(b) else b
    )
    return df


def add_engineered_features(df: pd.DataFrame, ref_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add numeric features. ref_df is used to compute brand/model medians (avoids target leakage)."""
    current_year = datetime.now(timezone.utc).year
    df = df.copy()
    df["age"] = (current_year - df["year"]).clip(lower=0)
    df["km_per_year"] = df["km"] / (df["age"] + 1)
    df["age_squared"] = df["age"] ** 2
    df["log_km"] = np.log1p(df["km"].clip(lower=0))
    df["log_age_plus1"] = np.log1p(df["age"].clip(lower=0))

    # Brand/model median price — encode market position signal
    # Use ref_df if provided (train set only) to prevent leakage at predict time
    src = ref_df if ref_df is not None else df
    brand_med = src.groupby("brand")[TARGET].median()
    model_med = src.groupby("model")[TARGET].median()
    global_med = float(src[TARGET].median())

    df["brand_median_price"] = df["brand"].map(brand_med).fillna(global_med)
    df["model_median_price"] = df["model"].map(model_med).fillna(
        df["brand"].map(brand_med).fillna(global_med)
    )
    return df


def dedup_data(df: pd.DataFrame) -> pd.DataFrame:
    """Remove near-duplicate rows (same brand+year+km+price)."""
    before = len(df)
    df = df.drop_duplicates(subset=["brand", "year", "km", "listed_price"], keep="first")
    removed = before - len(df)
    if removed:
        print(f"Removed {removed} duplicate rows.")
    return df


# ---------------------------------------------------------------------------
# TRAINING
# ---------------------------------------------------------------------------
def _build_pipeline(**kwargs) -> Pipeline:
    """OrdinalEncoder for categoricals + LGBMRegressor."""
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
    
    params = {
        "n_estimators": 400,
        "max_depth": 8,
        "learning_rate": 0.05,
        "min_child_samples": 20,
        "random_state": 42,
        "verbose": -1,
    }
    params.update(kwargs)
    
    lgbm = LGBMRegressor(**params)
    return Pipeline([("prep", pre), ("lgbm", lgbm)])


def remove_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Remove price outliers using IQR per brand/model and filter unrealistic km/year combinations."""
    before = len(df)
    
    # Basic bounds
    df = df[(df[TARGET] >= 50_000) & (df[TARGET] <= 20_000_000)]
    
    # KM/Year sanity checks
    current_year = datetime.now(timezone.utc).year
    df = df[df["year"] >= 1990]
    df = df[df["year"] <= current_year + 1]
    
    age = current_year - df["year"]
    max_km_allowed = (age + 1) * 100_000
    df = df[df["km"] <= max_km_allowed]
    df = df[df["km"] <= 1_500_000]

    # IQR based price filtering — brand level only (model groups are too small).
    # Rows in brands with fewer than 10 samples are kept as-is to avoid
    # accidentally discarding all data for rare makes.
    brand_counts = df.groupby("brand")[TARGET].transform("count")
    Q1 = df.groupby("brand")[TARGET].transform(lambda x: x.quantile(0.25))
    Q3 = df.groupby("brand")[TARGET].transform(lambda x: x.quantile(0.75))
    IQR = Q3 - Q1

    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    mask = (brand_counts < 10) | ((df[TARGET] >= lower_bound) & (df[TARGET] <= upper_bound))
    df = df[mask]
    
    removed = before - len(df)
    if removed:
        print(f"Removed {removed} outlier rows based on IQR and sanity checks.")
    
    return df


def _prepare_data_for_training() -> tuple[pd.DataFrame, str]:
    df = export_dataframe()
    source = "database"
    print(f"DB'de {len(df)} kayıt var. Arabam.com'dan ek veri çekiliyor…")
    df_arabam = pd.DataFrame(scrape_arabam_listings())

    if _SAHIBINDEN_AVAILABLE:
        print("Sahibinden.com'dan ek veri çekiliyor…")
        df_sahibinden = pd.DataFrame(scrape_sahibinden_listings(max_pages=20))
    else:
        print("Sahibinden.com scraper mevcut değil (nodriver yok), atlanıyor.")
        df_sahibinden = pd.DataFrame()

    print("fordikinciel.com'dan ek veri çekiliyor…")
    df_ford = pd.DataFrame(scrape_fordikinciel_listings(max_pages=80))

    print("otosor.com.tr'den ek veri çekiliyor…")
    df_otosor = pd.DataFrame(scrape_otosor_listings(max_pages=250))

    print("araba.com'dan ek veri çekiliyor…")
    df_araba = pd.DataFrame(scrape_araba_listings(max_pages=15))

    print("otoplus.com.tr'den ek veri çekiliyor…")
    df_otoplus = pd.DataFrame(scrape_otoplus_listings())

    print("otoshops.com'dan ek veri çekiliyor…")
    df_otoshops = pd.DataFrame(scrape_otoshops_listings())

    df = pd.concat([df, df_arabam, df_sahibinden, df_ford, df_otosor, df_araba, df_otoplus, df_otoshops], ignore_index=True)
    df = df.dropna(subset=["brand", "year", "km", TARGET])
    source = f"arabam.com + sahibinden.com + fordikinciel.com + otosor.com.tr + araba.com + otoplus.com.tr + otoshops.com + database ({len(df)} toplam)"

    if len(df) < 5:
        raise RuntimeError(
            "Yeterli eğitim verisi yok. Arabam.com scraper'ının çalıştığından emin olun."
        )

    df = normalize_brands(df)
    df = remove_outliers(df)
    df = dedup_data(df)

    for col in ["model", "city", "body_type"]:
        if col not in df.columns:
            df[col] = None
    if "has_damage" not in df.columns:
        df["has_damage"] = 0
    else:
        df["has_damage"] = df["has_damage"].fillna(0).astype(int)

    df = add_engineered_features(df)
    df[LOG_TARGET] = np.log1p(df[TARGET])

    return df, source

def train(verbose: bool = True, use_best_params: bool = True, _df=None, _source=None) -> Pipeline:
    import joblib

    if _df is not None:
        df, source = _df, (_source or "preloaded")
    else:
        df, source = _prepare_data_for_training()

    best_params = {}
    best_params_path = Path(__file__).parent / "best_params.json"
    if use_best_params and best_params_path.exists():
        try:
            best_params = json.loads(best_params_path.read_text(encoding="utf-8"))
            if verbose:
                print(f"Optuna'nın bulduğu en iyi ayarlar kullanılıyor: {best_params}")
        except Exception:
            pass

    X = df[FEATURES]
    # Train on log(price) — car price is log-normal, this significantly improves R²
    y_log = df[LOG_TARGET]
    y_real = df[TARGET]

    X_train, X_test, y_log_train, y_log_test, y_real_train, y_real_test = train_test_split(
        X, y_log, y_real, test_size=0.2, random_state=42
    )

    cat_indices = list(range(len(CATEGORICAL)))

    # 5-fold cross-validation on log target
    if verbose:
        print("5-Fold CV çalışıyor…")
    cv_pipe = _build_pipeline(**best_params)
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_r2_scores = cross_val_score(
        cv_pipe, X, y_log,
        cv=kf,
        scoring="r2",
    )
    cv_r2_mean = float(np.mean(cv_r2_scores))
    cv_r2_std  = float(np.std(cv_r2_scores))

    # Final model trained on log(price)
    pipe = _build_pipeline(**best_params)
    pipe.fit(X_train, y_log_train, lgbm__categorical_feature=cat_indices)

    joblib.dump(pipe, MODEL_PATH)

    # Back-transform predictions to TRY for MAE, compute R² on real prices
    pred_log_train = pipe.predict(X_train)
    pred_log_test  = pipe.predict(X_test)
    pred_train = np.expm1(pred_log_train)
    pred_test  = np.expm1(pred_log_test)

    train_mae = mean_absolute_error(y_real_train, pred_train)
    test_mae  = mean_absolute_error(y_real_test,  pred_test)
    test_r2   = r2_score(y_real_test, pred_test)

    # Save brand/model medians for use at predict time
    brand_medians = df.groupby("brand")[TARGET].median().to_dict()
    model_medians = df.groupby("model")[TARGET].median().to_dict()
    global_median = float(df[TARGET].median())

    meta = {
        "trained_at":    datetime.now(timezone.utc).isoformat(),
        "row_count":     len(df),
        "source":        source,
        "train_mae":     round(float(train_mae), 2),
        "test_mae":      round(float(test_mae), 2),
        "test_r2":       round(float(test_r2), 4),
        "cv_r2_mean":    round(cv_r2_mean, 4),
        "cv_r2_std":     round(cv_r2_std, 4),
        "global_median": global_median,
        "brand_medians": brand_medians,
        "model_medians": model_medians,
    }
    MODEL_META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if verbose:
        print(f"Trained on {len(df)} rows ({source}).")
        print(f"  Train MAE:  {train_mae:,.0f} TRY")
        print(f"  Test  MAE:  {test_mae:,.0f} TRY")
        print(f"  Test  R²:   {test_r2:.3f}")
        print(f"  CV    R²:   {cv_r2_mean:.3f} ± {cv_r2_std:.3f}")
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

    current_year = datetime.now(timezone.utc).year
    age = max(current_year - year, 0)
    norm_brand = BRAND_ALIASES.get(str(brand).lower().strip(), str(brand).strip())

    # Load saved medians for brand/model features
    meta_info: dict = {}
    if MODEL_META_PATH.exists():
        try:
            meta_info = json.loads(MODEL_META_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    global_med = meta_info.get("global_median", 800_000)
    brand_meds = meta_info.get("brand_medians", {})
    model_meds = meta_info.get("model_medians", {})
    brand_med_val = brand_meds.get(norm_brand, global_med)
    model_med_val = model_meds.get(model or "", brand_med_val)

    X = pd.DataFrame(
        [{
            "brand":              norm_brand,
            "model":              model,
            "fuel_type":          fuel_type,
            "transmission":       transmission,
            "city":               city,
            "body_type":          body_type,
            "year":               year,
            "km":                 km,
            "has_damage":         int(has_damage) if has_damage is not None else 0,
            "age":                age,
            "km_per_year":        km / (age + 1),
            "age_squared":        age ** 2,
            "log_km":             np.log1p(max(km, 0)),
            "log_age_plus1":      np.log1p(age),
            "brand_median_price": brand_med_val,
            "model_median_price": model_med_val,
        }],
        columns=FEATURES,
    )
    pred_log = pipe.predict(X)[0]
    return int(round(np.expm1(pred_log)))


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
def optimize(n_trials: int = 50):
    import optuna
    
    print("Veri hazırlanıyor...")
    df, _src = _prepare_data_for_training()
    
    X = df[FEATURES]
    y_log = df[LOG_TARGET]

    X_train, X_test, y_log_train, y_log_test = train_test_split(
        X, y_log, test_size=0.2, random_state=42
    )

    cat_indices = list(range(len(CATEGORICAL)))

    def objective(trial):
        params = {
            "n_estimators":      trial.suggest_int("n_estimators", 200, 2000, step=100),
            "max_depth":         trial.suggest_int("max_depth", 4, 14),
            "num_leaves":        trial.suggest_int("num_leaves", 31, 511),
            "learning_rate":     trial.suggest_float("learning_rate", 0.005, 0.15, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 60),
            "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_alpha":         trial.suggest_float("reg_alpha", 1e-5, 5.0, log=True),
            "reg_lambda":        trial.suggest_float("reg_lambda", 1e-5, 5.0, log=True),
        }
        pipe = _build_pipeline(**params)
        pipe.fit(X_train, y_log_train, lgbm__categorical_feature=cat_indices)
        preds_log = pipe.predict(X_test)
        # Optimize on R² of back-transformed prices
        preds_real = np.expm1(preds_log)
        real_test = np.expm1(y_log_test)
        return -r2_score(real_test, preds_real)

    print("Optuna optimizasyonu başlıyor...")
    optuna.logging.set_verbosity(optuna.logging.INFO)
    study = optuna.create_study(direction="minimize")  # minimizing -R² = maximizing R²
    study.optimize(objective, n_trials=n_trials)
    
    print("\nEn iyi parametreler:")
    print(json.dumps(study.best_params, indent=2))
    
    best_params_path = Path(__file__).parent / "best_params.json"
    best_params_path.write_text(json.dumps(study.best_params, indent=2), encoding="utf-8")
    print(f"Parametreler kaydedildi: {best_params_path}")
    
    print("Yeni ayarlarla final model eğitiliyor...")
    train(verbose=True, use_best_params=True, _df=df, _source=_src)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "export":
        frame = export_dataframe()
        print(f"{len(frame)} usable rows in the database:")
        print(frame.head(20).to_string())
    elif cmd == "train":
        train()
    elif cmd == "optimize":
        optimize(n_trials=30)
    else:
        print("Usage: python ml.py [train|export|optimize]")
