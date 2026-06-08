"""
ratelimit.py — simple daily request caps, ISOLATED here.

Two ceilings, both reset each calendar day:
  - PER_IP_DAILY_CAP : one visitor can't hog the shared free-tier quota
  - GLOBAL_DAILY_CAP : the whole app stays under Gemini's free RPD (20) with headroom

We persist counts in SQLite (UsageRecord) so the limits survive server restarts.
This is intentionally lightweight (IP-based) — it deters casual overuse, not a
determined attacker with a VPN. Upgrade path: replace `client_ip` identity with
an authenticated user id (e.g. Google OAuth) and the same counters still work.

Tunables — raise these once you move to Gemini's paid tier.
"""

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import UsageRecord

# Config from .env so caps/exemptions are tunable per environment WITHOUT code
# changes — loose while developing, strict in production.
load_dotenv(Path(__file__).parent / ".env")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


PER_IP_DAILY_CAP = _int_env("RATE_LIMIT_PER_IP", 3)
GLOBAL_DAILY_CAP = _int_env("RATE_LIMIT_GLOBAL", 18)

# IPs that bypass the limits entirely — the operator, not untrusted visitors.
# Defaults to localhost so local development is never throttled. In production,
# real users arrive on external IPs (via X-Forwarded-For) and stay limited.
EXEMPT_IPS = {
    ip.strip()
    for ip in os.getenv("RATE_LIMIT_EXEMPT_IPS", "127.0.0.1,::1,localhost").split(",")
    if ip.strip()
}


def is_exempt(ip: str) -> bool:
    return ip in EXEMPT_IPS


def client_ip(request: Request) -> str:
    """Best-effort client IP. Honor X-Forwarded-For first (in case we sit behind
    a proxy), else fall back to the direct socket address."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _today() -> str:
    return date.today().isoformat()


def _global_count(db: Session, day: str) -> int:
    total = db.query(func.coalesce(func.sum(UsageRecord.count), 0)).filter(
        UsageRecord.day == day
    ).scalar()
    return int(total)


def _ip_row(db: Session, ip: str, day: str) -> UsageRecord | None:
    return (
        db.query(UsageRecord)
        .filter(UsageRecord.ip == ip, UsageRecord.day == day)
        .one_or_none()
    )


def enforce_limits(db: Session, ip: str) -> None:
    """Raise HTTP 429 if this request would exceed either cap. Call BEFORE doing
    the expensive Gemini work."""
    if is_exempt(ip):
        return  # operator / localhost — never throttled

    day = _today()

    if _global_count(db, day) >= GLOBAL_DAILY_CAP:
        raise HTTPException(
            status_code=429,
            detail=f"Günlük genel analiz limiti ({GLOBAL_DAILY_CAP}) doldu. Yarın tekrar dene.",
        )

    row = _ip_row(db, ip, day)
    if row and row.count >= PER_IP_DAILY_CAP:
        raise HTTPException(
            status_code=429,
            detail=f"Bugünkü analiz hakkın ({PER_IP_DAILY_CAP}) doldu. Yarın tekrar dene.",
        )


def record_usage(db: Session, ip: str) -> None:
    """Increment this IP's counter for today. Call AFTER a successful analysis."""
    if is_exempt(ip):
        return  # keep operator activity off the ledger (don't eat the global cap)

    day = _today()
    row = _ip_row(db, ip, day)
    if row is None:
        db.add(UsageRecord(ip=ip, day=day, count=1))
    else:
        row.count += 1
    db.commit()


def usage_status(db: Session, ip: str) -> dict:
    """Snapshot of remaining quota for this IP — surfaced in the UI."""
    day = _today()
    row = _ip_row(db, ip, day)
    used = row.count if row else 0
    exempt = is_exempt(ip)
    return {
        "used": used,
        "limit": PER_IP_DAILY_CAP,
        "remaining": max(0, PER_IP_DAILY_CAP - used),
        "global_used": _global_count(db, day),
        "global_limit": GLOBAL_DAILY_CAP,
        "exempt": exempt,
    }
