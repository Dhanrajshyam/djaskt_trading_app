"""Liveness and readiness endpoints (Kubernetes/Docker Compose convention).

Two separate endpoints, not one merged health check, matching the standard
Kubernetes probe split:

- `/healthz` (liveness): "is the process up and able to respond at all."
  Never checks external dependencies — if it did, a temporary Postgres or
  Redis outage would make Kubernetes conclude the *pod* is broken and kill
  + restart it, which doesn't fix a database outage and just adds
  restart-loop noise on top of an already-degraded dependency.
- `/readyz` (readiness): "is the process ready to serve real traffic,"
  checking every hard dependency (primary + replica Postgres, Redis).
  Kubernetes uses this to decide whether to route traffic to this pod at
  all — a pod can be alive but not ready (e.g. still warming up, or a
  dependency is down) without needing to be restarted.

Deliberately outside `/api/v1/` — orchestrators probing liveness/readiness
shouldn't need to know or track this app's API version.
"""

from django.http import HttpRequest, JsonResponse

from extensions.health import check_database, check_redis


def liveness(request: HttpRequest) -> JsonResponse:
    """Liveness probe: 200 if this process can respond at all.

    No dependency checks by design — see module docstring.
    """
    return JsonResponse({"status": "ok"})


def readiness(request: HttpRequest) -> JsonResponse:
    """Readiness probe: 200 only if every hard dependency is reachable.

    Checks both Postgres connections (primary "default" and "replica" —
    see `django_app.settings.DATABASES`) and the shared Redis client.
    Returns 503 with a per-dependency breakdown if anything is down, so an
    operator (or `kubectl describe pod`) can see which dependency failed
    without needing to cross-reference logs first.
    """
    checks = {
        "database": check_database("default"),
        "replica": check_database("replica"),
        "redis": check_redis(),
    }
    healthy = all(checks.values())
    status_code = 200 if healthy else 503
    return JsonResponse(
        {"status": "ok" if healthy else "unavailable", "checks": checks},
        status=status_code,
    )
