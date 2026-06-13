"""ntfy.sh push alerts (VOX-004, and L2 of the escalation chain).

A caregiver subscribes to a private ntfy topic; we POST a message to it. The request
*builder* is a pure function so it can be unit-tested without network; ``send_alert``
does the actual HTTP POST (requests imported lazily).
"""

from __future__ import annotations

DEFAULT_BASE = "https://ntfy.sh"


def build_request(
    topic: str,
    message: str,
    title: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    base: str = DEFAULT_BASE,
) -> tuple[str, dict[str, str], bytes]:
    """Return ``(url, headers, body)`` for an ntfy POST. No I/O."""
    if not topic:
        raise ValueError("ntfy topic is required")
    url = f"{base.rstrip('/')}/{topic}"
    headers: dict[str, str] = {}
    if title:
        headers["Title"] = title
    if priority:
        headers["Priority"] = priority
    if tags:
        headers["Tags"] = ",".join(tags)
    return url, headers, message.encode("utf-8")


def send_alert(
    topic: str,
    message: str,
    title: str | None = None,
    priority: str = "high",
    tags: list[str] | None = None,
    base: str = DEFAULT_BASE,
    timeout: float = 10.0,
) -> int:
    """POST an alert to ntfy.sh. Returns the HTTP status code; raises on HTTP error."""
    import requests  # lazy

    url, headers, body = build_request(topic, message, title, priority, tags, base)
    resp = requests.post(url, data=body, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.status_code
