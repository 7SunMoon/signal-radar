from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", without_tags).strip()


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def stable_id(url: str, title: str = "") -> str:
    basis = canonicalize_url(url) or clean_text(title).lower()
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:14]


def normalize_title(title: str) -> str:
    lowered = clean_text(title).lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", lowered).strip()


def iso_from_timestamp(timestamp: int | float | None) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: str | None) -> str:
    if not value:
        return ""
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
