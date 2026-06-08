import os
import pandas as pd
from scraper_arabam import scrape_arabam_listings
from ml import export_dataframe, _build_pipeline, FEATURES, TARGET, MODEL_PATH
import joblib
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

DATASET_PATH = "arabam_dataset.csv"
PAGES_TO_SCRAPE = 100 # Approx 2000 cars. Going beyond 100 might trigger anti-bot.

def main():
    print(f"Starting massive data collection: scraping {PAGES_TO_SCRAPE} pages...")
    
    # 1. Scrape data
    scraped_data = scrape_arabam_listings(pages=PAGES_TO_SCRAPE)
    df_scraped = pd.DataFrame(scraped_data)
    
    print(f"Scraped {len(df_scraped)} listings. Saving to {DATASET_PATH}...")
    df_scraped.to_csv(DATASET_PATH, index=False)
    
    # 2. Export existing DB data
    df_db = export_dataframe()
    print(f"Loaded {len(df_db)} existing rows from database.")
    
    # 3. Combine
    df = pd.concat([df_db, df_scraped], ignore_index=True)
    df = df.dropna(subset=FEATURES + [TARGET])
    
    if len(df) < 50:
        print("Not enough data to train. Exiting.")
        return
        
    print(f"Training RandomForest on {len(df)} total rows...")
    
    # 4. Train
    X = df[FEATURES]
    y = df[TARGET]
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    pipe = _build_pipeline()
    pipe.fit(X_train, y_train)
    
    joblib.dump(pipe, MODEL_PATH)
    
    # 5. Report
    train_mae = mean_absolute_error(y_train, pipe.predict(X_train))
    test_mae = mean_absolute_error(y_test, pipe.predict(X_test))
    test_r2 = r2_score(y_test, pipe.predict(X_test))
    
    print("========================================")
    print(f"MASSIVE TRAINING COMPLETE!")
    print(f"  Total Rows : {len(df)}")
    print(f"  Train MAE  : {train_mae:,.0f} TRY")
    print(f"  Test  MAE  : {test_mae:,.0f} TRY")
    print(f"  Test  R^2  : {test_r2:.3f}")
    print("========================================")

if __name__ == "__main__":
    main()
