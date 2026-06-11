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
PER_USER_DAILY_CAP = _int_env("RATE_LIMIT_PER_USER", 100)
GLOBAL_DAILY_CAP = _int_env("RATE_LIMIT_GLOBAL", 200)

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


def get_identity(ip: str, user: dict | None) -> tuple[str, int]:
    """Return (identity_key, daily_cap).
    Logged-in users get a higher cap keyed by user ID; guests are keyed by IP.
    """
    if user and user.get("sub"):
        return f"user:{user['sub']}", PER_USER_DAILY_CAP
    return ip, PER_IP_DAILY_CAP


def enforce_limits(db: Session, ip: str, user: dict | None = None) -> None:
    """Raise HTTP 429 if this request would exceed either cap. Call BEFORE doing
    the expensive Gemini work."""
    if is_exempt(ip):
        return  # operator / localhost — never throttled

    identity, cap = get_identity(ip, user)
    day = _today()

    if _global_count(db, day) >= GLOBAL_DAILY_CAP:
        raise HTTPException(
            status_code=429,
            detail=f"Günlük genel analiz limiti ({GLOBAL_DAILY_CAP}) doldu. Yarın tekrar dene.",
        )

    row = _ip_row(db, identity, day)
    if row and row.count >= cap:
        if user:
            raise HTTPException(
                status_code=429,
                detail=f"Bugünkü analiz hakkın ({cap}) doldu. Yarın tekrar dene.",
            )
        raise HTTPException(
            status_code=429,
            detail=f"Misafir günlük limit ({cap}) doldu. Giriş yaparak daha fazla analiz hakkı kazanabilirsin.",
        )


def record_usage(db: Session, ip: str, user: dict | None = None) -> None:
    """Increment the identity's counter for today. Call AFTER a successful analysis."""
    if is_exempt(ip):
        return

    identity, _ = get_identity(ip, user)
    day = _today()
    row = _ip_row(db, identity, day)
    if row is None:
        db.add(UsageRecord(ip=identity, day=day, count=1))
    else:
        row.count += 1
    db.commit()


def usage_status(db: Session, ip: str, user: dict | None = None) -> dict:
    """Snapshot of remaining quota — surfaced in the UI."""
    identity, cap = get_identity(ip, user)
    day = _today()
    row = _ip_row(db, identity, day)
    used = row.count if row else 0
    exempt = is_exempt(ip)
    return {
        "used": used,
        "limit": cap,
        "remaining": max(0, cap - used),
        "global_used": _global_count(db, day),
        "global_limit": GLOBAL_DAILY_CAP,
        "exempt": exempt,
    }
