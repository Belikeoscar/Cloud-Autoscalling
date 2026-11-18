import requests, pandas as pd, sys
from datetime import datetime, timedelta, timezone

P = "http://localhost:9090/api/v1/query_range"
end = datetime.now(timezone.utc)
start = end - timedelta(minutes=int(sys.argv[1]) if len(sys.argv) > 1 else 60)

queries = {
 "req_rate": 'sum(rate(http_requests_total{job="scaling-app",handler="/work"}[1m]))',
 "cpu_cores": 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"scaling-app-.*",container="scaling-app"}[1m]))',
 "replicas": 'max(kube_deployment_status_replicas{deployment="scaling-app"})',
}
frames = []
for name, q in queries.items():
    r = requests.get(P, params={"query": q, "start": start.timestamp(),
                                "end": end.timestamp(), "step": "15s"}).json()
    res = r["data"]["result"]
    print(name, "series:", len(res))
    if not res:
        continue
    frames.append(pd.DataFrame(res[0]["values"], columns=["ts", name]).set_index("ts").astype(float))
df = pd.concat(frames, axis=1).sort_index().reset_index()
df["time"] = pd.to_datetime(df["ts"], unit="s", utc=True)
df.to_csv("history_run2.csv", index=False)
print(df.describe()); print(len(df), "rows")
act = df[df["req_rate"] > 1]
print("Load first/last:", act["time"].min(), act["time"].max())
print("Requests (sum rate x 15):", round((df["req_rate"].fillna(0) * 15).sum()))
print("Max replicas:", df["replicas"].max())
