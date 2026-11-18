import pandas as pd
df = pd.read_csv("history_run1.csv")
step = 15  # seconds between samples
cpu_seconds = (df["cpu_cores"].fillna(0) * step).sum()
k6_requests = 116447
print("CPU-seconds from Prometheus:", round(cpu_seconds, 1))
print("Expected from k6 (x0.02):   ", round(k6_requests * 0.02, 1))
print("Ratio:", round(cpu_seconds / (k6_requests * 0.02), 3))
print("Max replicas:", df["replicas"].max())
print(df[["time","cpu_cores","replicas","req_rate_est"]].head(8))
