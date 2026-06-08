import pandas as pd
import joblib
import datetime
from scraper_arabam import scrape_arabam_listings
from ml import export_dataframe, _build_pipeline, FEATURES, TARGET, MODEL_PATH
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

DATASET_PATH = 'arabam_dataset.csv'

def run_daily_update():
    print(f"[{datetime.datetime.now()}] Starting daily data update & model retrain...")
    
    # 1. Scrape a few new pages
    new_data = scrape_arabam_listings(pages=10) # 200 cars
    df_new = pd.DataFrame(new_data)
    
    # 2. Load existing dataset
    try:
        df_existing = pd.read_csv(DATASET_PATH)
    except FileNotFoundError:
        df_existing = pd.DataFrame()
        
    # 3. Combine and save (drop exact duplicates if any)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.drop_duplicates(subset=['brand', 'model', 'year', 'km', 'listed_price'], inplace=True)
    df_combined.to_csv(DATASET_PATH, index=False)
    
    # 4. Filter outliers
    df_clean = df_combined[(df_combined['listed_price'] < 5_000_000) & (df_combined['listed_price'] > 150_000)]
    
    # 5. Add organically analyzed rows from database
    df_db = export_dataframe()
    df_final = pd.concat([df_clean, df_db], ignore_index=True)
    df_final.drop_duplicates(subset=['brand', 'model', 'year', 'km', 'listed_price'], inplace=True)
    df_final = df_final.dropna(subset=FEATURES + [TARGET])
    
    if len(df_final) < 50:
        print("Not enough data to train.")
        return

    # 6. Train model
    X = df_final[FEATURES]
    y = df_final[TARGET]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    pipe = _build_pipeline()
    pipe.fit(X_train, y_train)
    joblib.dump(pipe, MODEL_PATH)
    
    test_r2 = r2_score(y_test, pipe.predict(X_test))
    print(f"[{datetime.datetime.now()}] Daily retrain complete. Rows: {len(df_final)}, Test R2: {test_r2:.3f}")

if __name__ == "__main__":
    run_daily_update()
