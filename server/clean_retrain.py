import pandas as pd
import joblib
from ml import export_dataframe, _build_pipeline, FEATURES, TARGET, MODEL_PATH
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

df = pd.read_csv('arabam_dataset.csv')
# Remove insane outlier prices (e.g. 930 Million TRY) and too cheap prices
df = df[(df['listed_price'] < 5_000_000) & (df['listed_price'] > 150_000)]

X = df[FEATURES]
y = df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

pipe = _build_pipeline()
pipe.fit(X_train, y_train)

joblib.dump(pipe, MODEL_PATH)

print(f"Cleaned Rows: {len(df)}")
print(f"Test R2: {r2_score(y_test, pipe.predict(X_test)):.3f}")
print(f"Test MAE: {mean_absolute_error(y_test, pipe.predict(X_test)):.0f}")
