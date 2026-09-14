"""In-process HTTP counters with bounded, route-level labels."""

from collections import Counter, defaultdict
from threading import Lock

_lock = Lock()
_request_counts = Counter()
_request_duration_seconds = defaultdict(float)


def observe_request(*, method, route, status_code, duration_seconds):
    if status_code in {401, 403}:
        outcome = "denied"
    elif status_code >= 500:
        outcome = "error"
    elif status_code >= 400:
        outcome = "client_error"
    else:
        outcome = "success"
    key = (method, route, str(status_code), outcome)
    with _lock:
        _request_counts[key] += 1
        _request_duration_seconds[(method, route)] += duration_seconds


def snapshot_http_metrics():
    with _lock:
        return dict(_request_counts), dict(_request_duration_seconds)
