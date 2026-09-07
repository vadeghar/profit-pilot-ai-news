from datetime import datetime

from app.domain.models import MarketPhase
from app.services.market_phase import current_market_phase


def test_pre_market_before_open() -> None:
    assert current_market_phase(datetime.fromisoformat("2026-09-07T09:14:59+05:30")) == MarketPhase.PRE_MARKET


def test_market_hours_at_open_and_before_close() -> None:
    assert current_market_phase(datetime.fromisoformat("2026-09-07T09:15:00+05:30")) == MarketPhase.MARKET_HOURS
    assert current_market_phase(datetime.fromisoformat("2026-09-07T15:29:59+05:30")) == MarketPhase.MARKET_HOURS


def test_post_market_at_close() -> None:
    assert current_market_phase(datetime.fromisoformat("2026-09-07T15:30:00+05:30")) == MarketPhase.POST_MARKET


def test_weekend_is_post_market() -> None:
    assert current_market_phase(datetime.fromisoformat("2026-09-06T12:00:00+05:30")) == MarketPhase.POST_MARKET
