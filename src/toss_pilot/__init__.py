"""Pilot client for the Toss Securities Open API.

Read-first by design: market data and account reads are first-class; order
placement exists only behind an explicit dry-run gate (see toss_pilot.orders).
"""

from toss_pilot.client import TossInvestClient
from toss_pilot.errors import CredentialsMissing, LiveOrderBlocked, TossApiError

__version__ = "0.1.0"

__all__ = [
    "TossInvestClient",
    "TossApiError",
    "LiveOrderBlocked",
    "CredentialsMissing",
    "__version__",
]
