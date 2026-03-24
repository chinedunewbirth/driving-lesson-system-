from prometheus_client import (
    Counter, Histogram, Gauge, Info,
    generate_latest, CONTENT_TYPE_LATEST,
)
from flask import request, g
import time

# ── Application Info ──────────────────────────────────────
APP_INFO = Info('drivesmart', 'DriveSmart application metadata')
APP_INFO.info({
    'version': '1.0.0',
    'framework': 'flask',
    'service': 'driving-lesson-system',
})

# ── HTTP Metrics ──────────────────────────────────────────
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)
REQUESTS_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method'],
)

# ── Business Metrics ──────────────────────────────────────
LESSONS_BOOKED = Counter(
    'lessons_booked_total',
    'Total lessons booked',
)
PAYMENTS_PROCESSED = Counter(
    'payments_processed_total',
    'Total payments processed',
    ['status'],
)
ACTIVE_USERS = Gauge(
    'active_users',
    'Number of active user sessions',
)
NOTIFICATIONS_SENT = Counter(
    'notifications_sent_total',
    'Total notifications dispatched',
    ['channel'],
)
PAYOUT_REQUESTS = Counter(
    'payout_requests_total',
    'Instructor payout requests created',
)
CHATBOT_REQUESTS = Counter(
    'chatbot_requests_total',
    'AI chatbot messages processed',
    ['intent'],
)
DB_QUERY_LATENCY = Histogram(
    'db_query_duration_seconds',
    'Database query latency',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.5, 1],
)


def init_metrics(app):
    """Register Prometheus metrics middleware with the Flask app."""

    @app.before_request
    def _start_timer():
        g._prom_start = time.perf_counter()
        REQUESTS_IN_PROGRESS.labels(method=request.method).inc()

    @app.after_request
    def _record_metrics(response):
        if hasattr(g, '_prom_start'):
            latency = time.perf_counter() - g._prom_start
            endpoint = request.endpoint or 'unknown'
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(latency)
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status=response.status_code,
            ).inc()
        REQUESTS_IN_PROGRESS.labels(method=request.method).dec()
        return response

    @app.route('/metrics')
    def metrics():
        """Prometheus scrape endpoint."""
        from flask import Response
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
