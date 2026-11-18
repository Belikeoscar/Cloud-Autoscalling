import sys, time, math, csv, os, subprocess, argparse
import numpy as np, pandas as pd, joblib, requests

ap = argparse.ArgumentParser()
ap.add_argument("--live", action="store_true", help="actually scale (default is dry-run)")
ap.add_argument("--steps", type=int, default=20, help="number of 15 s cycles")
ap.add_argument("--out", default="controller_log.csv")
a = ap.parse_args()

PROM = "http://localhost:9090/api/v1/query"
Q_RATE = 'sum(rate(http_requests_total{job="scaling-app",handler="/work"}[1m]))'
Q_CPU = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"scaling-app-.*",container="scaling-app"}[1m]))'
DEPLOY = "scaling-app"
MIN_R, MAX_R = 1, 30
POD_REQ_CORES, TARGET = 0.1, 0.5
STEP_S, COOLDOWN_S = 15, 300

model = joblib.load("rf_h4.joblib")

# calibrate cores per request/s from the load window
h = pd.read_csv("history_run2.csv")
h["time"] = pd.to_datetime(h["time"])
h = h[(h["time"] >= pd.Timestamp("2026-11-10 01:02:00", tz="UTC")) &
      (h["time"] <= pd.Timestamp("2026-11-10 01:24:00", tz="UTC"))]
h = h[h["req_rate"] > 10]
CPR = float((h["cpu_cores"] / h["req_rate"]).median())
print(f"calibrated cores per req/s: {CPR:.5f}")

def qprom(expr, retries=3):
    for _ in range(retries):
        try:
            r = requests.get(PROM, params={"query": expr}, timeout=15).json()["data"]["result"]
            return float(r[0]["value"][1]) if r else float("nan")
        except Exception:
            time.sleep(2)
    return None


def get_replicas():
    try:
        out = subprocess.check_output(["kubectl", "get", "deploy", DEPLOY, "-o", "jsonpath={.status.replicas}"], text=True, timeout=20)
        return int(out or 1)
    except Exception:
        return None


def scale(n):
    """Return (ok, error_text). Never raises, so a failed scale cannot crash the loop."""
    try:
        subprocess.run(
            ["kubectl", "scale", "deploy", DEPLOY, f"--replicas={n}"],
            check=True, capture_output=True, text=True, timeout=30,
        )
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "kubectl_timeout"
    except subprocess.CalledProcessError as e:
        return False, "kubectl_error: " + (e.stderr or "").strip().replace("\n", " ")[:120]
    except Exception as e:
        return False, f"scale_exception: {e}"

buf, last_change = [], 0.0
new = not os.path.exists(a.out)
f = open(a.out, "a", newline="")
w = csv.writer(f)
if new:
    w.writerow(["time_utc", "rate", "cpu", "replicas", "pred_rate_60s", "raw_desired", "final_desired", "action", "note"])

for i in range(a.steps):
    t0 = time.time()
    rate, cpu, reps = qprom(Q_RATE), qprom(Q_CPU), get_replicas()
    if rate is None or cpu is None or reps is None:
        w.writerow([pd.Timestamp.now("UTC").isoformat(), "", "", reps, "", "", "", "hold", "prom_error"])
        f.flush()
        print(f"{i+1}/{a.steps} prom_error -> hold")
        time.sleep(max(0, STEP_S - (time.time() - t0)))
        continue

    note = ""
    if math.isnan(rate):
        rate, note = 0.0, "rate_missing_as_0"
    if math.isnan(cpu):
        cpu, note = 0.0, note + " cpu_missing_as_0"
    buf.append((rate, cpu)); buf = buf[-4:]
    pred = raw = final = None
    action = "warmup"
    if len(buf) == 4:
        r = [b[0] for b in reversed(buf)]
        c = [b[1] for b in reversed(buf)]
        feats = {"rate_lag1": r[0], "cpu_lag1": c[0], "rate_lag2": r[1], "cpu_lag2": c[1],
                 "rate_lag3": r[2], "cpu_lag3": c[2], "rate_lag4": r[3], "cpu_lag4": c[3],
                 "replicas_lag1": reps, "rate_roll4": float(np.mean(r)), "rate_diff1": r[0] - r[1]}
        X = pd.DataFrame([feats])[list(model.feature_names_in_)]
        pred = max(0.0, float(model.predict(X)[0]))
        if max(r) < 2.0:
            pred, note = r[0], (note + ' idle_guard').strip()
        raw = math.ceil(pred * CPR / (POD_REQ_CORES * TARGET))
        final = min(MAX_R, max(MIN_R, raw))
        action = "hold"
        if final > reps:
            action = "scale_up"
        elif final < reps:
            if time.time() - last_change >= COOLDOWN_S:
                action = "scale_down"
            else:
                action, final = "hold_cooldown", reps
        if action in ("scale_up", "scale_down"):
            if a.live:
                ok, err = scale(final)
                if ok:
                    last_change = time.time()
                else:
                    action = "scale_failed"
                    note = (note + " " + err).strip()
                    final = reps
            else:
                last_change = time.time()
                action += "_DRYRUN"

    w.writerow([pd.Timestamp.now("UTC").isoformat(), round(rate, 3), round(cpu, 5), reps,
                None if pred is None else round(pred, 2), raw, final, action, note.strip()])
    f.flush()
    print(f"{i+1}/{a.steps} rate={rate:.1f} cpu={cpu:.3f} reps={reps} pred60={pred} -> {action} {final}")
    time.sleep(max(0, STEP_S - (time.time() - t0)))
f.close()

