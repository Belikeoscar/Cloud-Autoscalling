import sys, os, time, json, platform
import numpy as np
import pandas as pd
import sklearn, joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ---- settings (edit if your header differs) ----
CSV = "history_run2.csv"
TIME_COL, RATE_COL, CPU_COL, REP_COL = "time", "req_rate", "cpu_cores", "replicas"
HORIZON = int(sys.argv[1]) if len(sys.argv) > 1 else 1   # steps of 15 s
LAGS = [1, 2, 3, 4]
TRAIN_FRAC = 0.70
SEED = 42
N_TREES = 200

# ---- load and order by time ----
df = pd.read_csv(CSV)
df[TIME_COL] = pd.to_datetime(df[TIME_COL])
df = df.sort_values(TIME_COL).reset_index(drop=True)
df = df[(df[TIME_COL] >= pd.Timestamp("2026-11-10 01:02:00", tz="UTC")) & (df[TIME_COL] <= pd.Timestamp("2026-11-10 01:24:00", tz="UTC"))].reset_index(drop=True)

# ---- features: only past information ----
feat = pd.DataFrame({TIME_COL: df[TIME_COL]})
for L in LAGS:
    feat[f"rate_lag{L}"] = df[RATE_COL].shift(L - 1)
    feat[f"cpu_lag{L}"] = df[CPU_COL].shift(L - 1)
feat["replicas_lag1"] = df[REP_COL]
feat["rate_roll4"] = df[RATE_COL].rolling(4).mean()
feat["rate_diff1"] = df[RATE_COL].diff()
feat["target"] = df[RATE_COL].shift(-HORIZON)
feat["naive"] = df[RATE_COL]
feat = feat.dropna().reset_index(drop=True)

# ---- chronological split ----
cut = int(len(feat) * TRAIN_FRAC)
train, test = feat.iloc[:cut], feat.iloc[cut:]
assert train[TIME_COL].max() < test[TIME_COL].min(), "Leakage: overlap"
cols = [c for c in feat.columns if c not in (TIME_COL, "target", "naive")]

# ---- fit ----
rf = RandomForestRegressor(n_estimators=N_TREES, random_state=SEED, n_jobs=-1)
t0 = time.perf_counter()
rf.fit(train[cols], train["target"])
train_s = time.perf_counter() - t0

# ---- predict and time inference ----
t0 = time.perf_counter()
pred = rf.predict(test[cols])
batch_s = time.perf_counter() - t0
t0 = time.perf_counter()
for i in range(20):
    rf.predict(test[cols].iloc[[i % len(test)]])
single_ms = (time.perf_counter() - t0) / 20 * 1000

def rmse(y, p):
    return float(np.sqrt(mean_squared_error(y, p)))

y = test["target"]
res = {
    "horizon_steps": HORIZON, "horizon_seconds": HORIZON * 15,
    "rows_total": len(feat), "rows_train": len(train), "rows_test": len(test),
    "train_window": [str(train[TIME_COL].min()), str(train[TIME_COL].max())],
    "test_window": [str(test[TIME_COL].min()), str(test[TIME_COL].max())],
    "RF_MAE": float(mean_absolute_error(y, pred)), "RF_RMSE": rmse(y, pred),
    "naive_MAE": float(mean_absolute_error(y, test["naive"])),
    "naive_RMSE": rmse(y, test["naive"]),
    "test_target_mean": float(y.mean()), "test_target_max": float(y.max()),
    "train_target_max": float(train["target"].max()),
    "train_seconds": train_s, "inference_single_ms": single_ms,
    "inference_batch_ms": batch_s * 1000,
    "features": cols, "n_trees": N_TREES, "seed": SEED,
    "python": platform.python_version(), "sklearn": sklearn.__version__,
    "pandas": pd.__version__, "numpy": np.__version__,
}
fn = f"rf_h{HORIZON}.joblib"
joblib.dump(rf, fn)
res["model_file_kb"] = os.path.getsize(fn) / 1024
imp = sorted(zip(cols, rf.feature_importances_), key=lambda x: -x[1])[:5]
res["top_features"] = [(n, round(float(v), 3)) for n, v in imp]
print(json.dumps(res, indent=2))
