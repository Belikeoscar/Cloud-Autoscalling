import requests, pandas as pd, sys
from datetime import datetime, timedelta, timezone

P = "http://localhost:9090/api/v1/query_range"
end = datetime.now(timezone.utc)
start = end - timedelta(minutes=int(sys.argv[1]) if len(sys.argv) > 1 else 60)

queries = {
 "req_rate": 'sum(rate(http_requests_total{job="scaling-app",handler="/work"}[1m]))',
 "req_total": 'sum(http_requests_total{job="scaling-app",handler="/work"})',
 "cpu_cores": 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"scaling-app-.*",container="scaling-app"}[1m]))',
 "replicas": 'kube_deployment_status_replicas{deployment="scaling-app"}',
 "replicas_ready": 'kube_deployment_status_replicas_ready{deployment="scaling-app"}',
}
frames = []
for name, q in queries.items():
    r = requests.get(P, params={"query": q, "start": start.timestamp(),
                                "end": end.timestamp(), "step": "15s"}).json()
    res = r["data"]["result"]
    if not res:
        print("NO DATA for", name); continue
    frames.append(pd.DataFrame(res[0]["values"], columns=["ts", name]).set_index("ts").astype(float))
df = pd.concat(frames, axis=1).reset_index()
df["time"] = pd.to_datetime(df["ts"], unit="s", utc=True)
df.to_csv("history_run2.csv", index=False)
print(df.describe()); print(len(df), "rows")
