# app/metrics/prometheus.py
from prometheus_fastapi_instrumentator import Instrumentator

def init_metrics(app):
    """
    Initializes Prometheus metrics instrumentation.
    Exposes /metrics endpoint for scraping.
    """
    Instrumentator().instrument(app).expose(app)