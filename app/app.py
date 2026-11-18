from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
import time

app = FastAPI()
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/work")
def work():
    # Busy-loop for about 20 ms to simulate CPU work per request
    end = time.perf_counter() + 0.02
    x = 0
    while time.perf_counter() < end:
        x += 1
    return {"done": True}
