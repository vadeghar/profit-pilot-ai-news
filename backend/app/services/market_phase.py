from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.domain.models import MarketPhase

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def current_market_phase(now: datetime | None = None) -> MarketPhase:
    """Return the conservative NSE phase for the supplied/current IST time.

    Weekends are treated as POST_MARKET. The exchange holiday calendar is
    intentionally outside this MVP helper; callers can replace this boundary
    with a full NSE calendar later without changing the processing pipeline.
    """
    current = (now or datetime.now(IST)).astimezone(IST)
    if current.weekday() >= 5:
        return MarketPhase.POST_MARKET
    if current.time() < MARKET_OPEN:
        return MarketPhase.PRE_MARKET
    if current.time() < MARKET_CLOSE:
        return MarketPhase.MARKET_HOURS
    return MarketPhase.POST_MARKET
