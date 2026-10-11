"""Deterministic, deliberately limited annual fundamentals and daily-bar research."""
from __future__ import annotations

import math
import statistics
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from toss_pilot.config import REPO_ROOT
from .store import Store, digest, instant

ENGINE_VERSION = "0.2.0"
_packaged = Path(__file__).resolve().parents[1] / "data" / "research.json"
DEFAULT_ASSUMPTIONS = json.loads(
    (_packaged if _packaged.is_file() else REPO_ROOT / "config" / "research.json").read_text(encoding="utf-8"))
SPECIAL_SECTORS = {"financials", "bank", "insurance", "reit", "biotech", "unknown"}


def rounded(value: float | Decimal | None, digits: int = 4):
    if value is None:
        return None
    return round(float(value), digits)


def ratio(a, b):
    return None if a is None or b is None or b <= 0 else a / b


def drawdown_series(prices: list[float]) -> tuple[list[float], float, int]:
    peak, longest, current = prices[0], 0, 0
    result = []
    for price in prices:
        peak = max(peak, price)
        dd = price / peak - 1
        result.append(dd)
        current = current + 1 if dd < -1e-12 else 0
        longest = max(longest, current)
    return result, min(result), longest


def market_metrics(candles: list[dict]) -> dict:
    if not candles:
        return {"bars": 0}
    closes = [float(c["close"]) for c in candles]
    dd, worst, duration = drawdown_series(closes)
    returns = [b / a - 1 for a, b in zip(closes, closes[1:])]
    trs = [max(float(c["high"]) - float(c["low"]),
               abs(float(c["high"]) - previous), abs(float(c["low"]) - previous))
           for previous, c in zip(closes, candles[1:])]
    result = {
        "bars": len(closes), "last_close": candles[-1]["close"],
        "last_bar": candles[-1]["timestamp"],
        "price_drawdown_pct": rounded(dd[-1] * 100),
        "historical_max_drawdown_pct": rounded(worst * 100),
        "longest_underwater_observations": duration,
        "annualized_daily_volatility_pct": rounded(statistics.stdev(returns[-63:]) * math.sqrt(252) * 100)
            if len(returns) >= 20 else None,
        "atr_14": rounded(statistics.mean(trs[-14:])) if len(trs) >= 14 else None,
    }
    for n in (20, 60, 200):
        result[f"sma_{n}"] = rounded(statistics.mean(closes[-n:])) if len(closes) >= n else None
        result[f"return_{n}_observations_pct"] = rounded((closes[-1] / closes[-n-1] - 1) * 100) if len(closes) > n else None
    result["chart"] = [{"timestamp": c["timestamp"], "close": c["close"], "drawdown_pct": rounded(d * 100)}
                       for c, d in zip(candles, dd)]
    return result


def financial_metrics(facts: list[dict]) -> tuple[dict, dict, list[str]]:
    warnings = []
    if not facts:
        return {}, {}, ["No eligible annual financial facts"]
    # Latest statement period, never silently mix a newer income statement
    # with an older balance sheet. No quarterly-to-annual extrapolation.
    period = max(f["period_end"] for f in facts)
    selected = {f["metric"]: f for f in facts if f["period_end"] == period}
    values = {key: Decimal(f["value"]) for key, f in selected.items()}
    starts = {f.get("period_start") for f in selected.values() if f.get("period_start")}
    if len(starts) > 1:
        return {}, selected, ["Incompatible annual duration periods"]
    def div(a, b):
        return rounded(ratio(values.get(a), values.get(b)))
    fcf = None
    if "operating_cash_flow" in values and "capex" in values:
        if values["capex"] >= 0:
            fcf = values["operating_cash_flow"] - values["capex"]
        else:
            warnings.append("Negative capex sign needs source review; FCF withheld")
    result = {
        "period_end": period, "values": {k: f["value"] for k, f in selected.items()},
        "net_margin": div("net_income", "revenue"),
        "operating_margin": div("operating_income", "revenue"),
        "liabilities_to_equity": div("liabilities", "equity"),
        "operating_cash_conversion": div("operating_cash_flow", "net_income"),
        "free_cash_flow_proxy": str(fcf) if fcf is not None else None,
        "free_cash_flow_margin": rounded(ratio(fcf, values.get("revenue"))),
    }
    if values.get("equity", Decimal(1)) <= 0:
        warnings.append("Non-positive equity; leverage ratio withheld")
    return result, selected, warnings


def validate_assumptions(config: dict) -> None:
    if set(config) != set(DEFAULT_ASSUMPTIONS):
        raise ValueError("Assumption file must specify exactly the documented keys")
    for key, minimum in (("minimum_bars", 63), ("max_price_age_days", 0), ("max_financial_age_days", 1)):
        if type(config[key]) is not int or config[key] < minimum:
            raise ValueError(f"Invalid {key}")
    if type(config["valuation_years"]) is not int or not 1 <= config["valuation_years"] <= 5:
        raise ValueError("valuation_years must be 1-5")
    for key, lower, upper in (("entry_margin", 0, 1), ("atr_invalidation_multiple", 0, 20)):
        x = Decimal(str(config[key]))
        if not x.is_finite() or not lower <= x < upper:
            raise ValueError(f"Invalid {key}")
    if set(config["scenarios"]) != {"bear", "base", "bull"}:
        raise ValueError("Exactly bear/base/bull scenarios are required")
    for scenario in config["scenarios"].values():
        if set(scenario) != {"eps_growth", "terminal_pe", "discount_rate"}:
            raise ValueError("Invalid scenario keys")
        for key, lower, upper in (("eps_growth", -1, 1), ("terminal_pe", 0, 100), ("discount_rate", 0, 1)):
            x = Decimal(str(scenario[key]))
            if not x.is_finite() or not lower < x < upper:
                raise ValueError(f"Invalid scenario {key}")


def analyze(store: Store, identity: str, as_of: str, assumptions: dict | None = None) -> dict:
    config = assumptions if assumptions is not None else DEFAULT_ASSUMPTIONS
    validate_assumptions(config)
    as_of = instant(as_of)
    instrument = store.instrument(identity, as_of=as_of)
    candles, facts = store.observations(identity, as_of)
    market = market_metrics(candles)
    financial, selected, findings = financial_metrics(facts)
    price_issues, financial_issues = [], list(findings)
    if len(candles) < config["minimum_bars"]:
        price_issues.append(f"Need {config['minimum_bars']} daily bars; have {len(candles)}")
    if candles:
        age = (date.fromisoformat(as_of[:10]) - date.fromisoformat(candles[-1]["timestamp"][:10])).days
        if age > config["max_price_age_days"]:
            price_issues.append(f"Latest price is {age} calendar days old")
        if len({c["timestamp"][:10] for c in candles}) != len(candles):
            price_issues.append("Multiple bars per UTC day; daily-series identity needs review")
        if any((datetime.fromisoformat(b["timestamp"]) - datetime.fromisoformat(a["timestamp"])).days > 10
               for a, b in zip(candles, candles[1:])):
            price_issues.append("Price history has a gap over 10 calendar days")
    if financial:
        age = (date.fromisoformat(as_of[:10]) - date.fromisoformat(financial["period_end"])).days
        if age > config["max_financial_age_days"]:
            financial_issues.append(f"Annual financial period is {age} days old")
    for required in ("revenue", "net_income", "equity", "operating_cash_flow"):
        if required not in selected:
            financial_issues.append(f"Missing annual {required}")
    valuation_issues = list(financial_issues) + list(price_issues)
    if instrument.get("sector", "unknown").lower() in SPECIAL_SECTORS:
        valuation_issues.append("Sector requires a specialized valuation model or explicit classification")
    if instrument.get("per_share_basis_verified") is not True:
        valuation_issues.append("Per-share/split consistency has not been verified for this instrument")
    verified_through = instrument.get("per_share_basis_verified_through", "")
    if verified_through < as_of[:10]:
        valuation_issues.append("Per-share/split verification does not cover the analysis date")
    eps = Decimal(selected["eps"]["value"]) if "eps" in selected else None
    if eps is None or eps <= 0:
        valuation_issues.append("Positive annual diluted EPS unavailable")
    scenarios, pe = {}, None
    if not valuation_issues:
        price = Decimal(candles[-1]["close"])
        pe = rounded(price / eps)
        for name, values in config["scenarios"].items():
            growth, multiple, discount = (Decimal(str(values[k])) for k in ("eps_growth", "terminal_pe", "discount_rate"))
            estimate = eps * (1 + growth) ** config["valuation_years"] * multiple / (1 + discount) ** config["valuation_years"]
            scenarios[name] = {"present_value_proxy": rounded(estimate), "assumptions": values,
                               "gap_to_price_pct": rounded((estimate / price - 1) * 100)}
        if not scenarios["bear"]["present_value_proxy"] <= scenarios["base"]["present_value_proxy"] <= scenarios["bull"]["present_value_proxy"]:
            raise ValueError("Scenario values must be ordered bear <= base <= bull")
    timing = {"status": "insufficient_data" if price_issues else "descriptive_only", "horizon": "2-12 weeks"}
    if not price_issues:
        atr = market["atr_14"]
        reference = market["sma_20"]
        timing.update({
            "trend": "above_60_day_average" if float(market["last_close"]) > market["sma_60"] else "below_60_day_average",
            "entry_reference": reference,
            "invalidation_reference": rounded(max(0, reference - float(config["atr_invalidation_multiple"]) * atr)),
            "rule": "Observe a pullback near SMA20 only while price and SMA20 are above SMA60; evaluate before use.",
            "trigger_now": float(market["last_close"]) > market["sma_60"] and reference > market["sma_60"]
                           and abs(float(market["last_close"]) - reference) <= atr,
            "exit_review": "Review when the trend condition fails or the holding window expires; no execution.",
        })
    long_term = {"horizon": "6-24 months", "status": "insufficient_data" if valuation_issues else "scenario_only",
                 "scenarios": scenarios, "trailing_pe": pe}
    if scenarios:
        entry = scenarios["base"]["present_value_proxy"] * (1 - float(config["entry_margin"]))
        long_term.update(entry_review_below=rounded(entry),
                         valuation_screen="within_assumed_entry_range" if float(market["last_close"]) <= entry else "wait_for_price_or_revised_evidence",
                         exit_review="Recompute after new filings; review if cash generation deteriorates or price exceeds the assumed range.")
    input_ids = sorted({x["snapshot_id"] for x in candles + facts})
    return {
        "schema_version": 1, "engine_version": ENGINE_VERSION, "instrument": instrument,
        "as_of": as_of, "data_label": "SYNTHETIC DEMONSTRATION" if instrument.get("synthetic") else "SOURCE-ATTRIBUTED RESEARCH; CHECK COVERAGE AND FRESHNESS",
        "input_hash": digest({"candles": candles, "facts": facts, "instrument": instrument}),
        "assumptions_hash": digest(config), "assumptions": config, "snapshot_ids": input_ids,
        "market": market, "financials": financial, "short_horizon": timing, "long_horizon": long_term,
        "quality": {"price_issues": price_issues, "financial_issues": financial_issues,
                    "valuation_issues": sorted(set(valuation_issues))},
        "sources": [{"metric": k, **v} for k, v in sorted(selected.items())],
        "market_sources": sorted({c["source_url"] for c in candles}),
        "limitations": [
            "Numerical research only; no AI thesis, investment recommendation, or validated strategy edge.",
            "Historical price drawdown is not strategy drawdown or a bound on future loss; gaps can exceed stop references.",
            "Earnings valuation is a discounted terminal P/E scenario, excludes dividends, and is not a DCF or price forecast.",
            "CFO less reported PP&E capex is a limited free-cash-flow proxy, not cash available to equity holders.",
            "Annual statements only; no consensus estimates, peer dataset, TTM assembly, or portfolio/FX stress model yet.",
            "252-day volatility convention; observations and calendar-day freshness checks are not an exchange calendar.",
            "Both publication date and first collection date constrain historical reports; current downloads do not prove point-in-time coverage.",
        ],
    }
