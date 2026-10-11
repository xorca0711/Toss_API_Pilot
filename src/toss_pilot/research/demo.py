"""Deterministic invented examples; no downloaded prices or real-company claims."""
from datetime import date, timedelta
from decimal import Decimal

from .store import Store


def populate(store: Store) -> list[str]:
    identities = []
    for market, symbol, currency, scale in (("KR", "000001", "KRW", 1000), ("US", "DEMO", "USD", 1)):
        identity = store.register({
            "market": market, "symbol": symbol, "currency": currency,
            "name": f"Example {market} Industrial (fictional)", "sector": "industrials",
            "synthetic": True, "per_share_basis_verified": True,
            "per_share_basis_verified_through": "2026-10-11"})
        candles, day, i = [], date(2025, 8, 1), 0
        while day <= date(2026, 10, 9):
            if day.weekday() < 5:
                # A reproducible rise, decline, and recovery, no random number seed.
                close = Decimal(100) + Decimal(i) / 10 + Decimal((i % 30) - 15) / 5
                if 100 <= i < 160:
                    close -= Decimal(30) * (1 - Decimal(abs(i - 130)) / 30)
                close *= scale
                candles.append({
                    "timestamp": day.isoformat() + "T16:00:00+00:00", "currency": currency, "adjusted": True,
                    "open": str(close), "high": str(close + scale), "low": str(close - scale),
                    "close": str(close), "volume": "100000"})
                i += 1
            day += timedelta(days=1)
        facts = []
        for metric, value in {
            "revenue": 1000000, "net_income": 120000, "operating_income": 150000,
            "operating_cash_flow": 180000, "capex": 40000, "assets": 2000000,
            "equity": 1200000, "liabilities": 800000, "cash": 300000, "eps": 8,
        }.items():
            facts.append({
                "metric": metric, "value": str(value * scale), "period_end": "2025-12-31",
                "period_start": None if metric in {"assets","equity","liabilities","cash"} else "2025-01-01",
                "available_at": "2026-03-15T00:00:00+00:00", "filing_id": f"DEMO-{market}-2025",
                "basis": "annual", "unit": currency + "/shares" if metric == "eps" else currency,
                "tag": f"fixture:{metric}"})
        store.ingest(identity, "synthetic", "demonstration", {"candles": candles, "facts": facts},
                     fetched_at="2026-10-10T00:00:00+00:00", locator=f"fixture:{identity}",
                     candles=candles, facts=facts)
        identities.append(identity)
    return identities
