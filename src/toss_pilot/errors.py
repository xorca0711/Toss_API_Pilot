"""Exception types for the pilot client."""

from __future__ import annotations

from typing import Any


class TossApiError(Exception):
    """An error response from the API.

    Business endpoints wrap errors as {"error": {"requestId", "code",
    "message", "data"}}; the OAuth token endpoint uses the OAuth2-standard
    {"error", "error_description"} shape. Both are normalized here. Quote
    request_id when contacting Toss support.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str = "",
        request_id: str | None = None,
        data: Any = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        self.data = data
        detail = f"HTTP {status_code} {code}"
        if message:
            detail += f": {message}"
        if request_id:
            detail += f" (requestId={request_id})"
        super().__init__(detail)


class LiveOrderBlocked(Exception):
    """Raised when a live order path is invoked without the explicit opt-ins.
    Two layers enforce this: the orders.py wrappers (dry_run default plus the
    TOSS_PILOT_ALLOW_LIVE_ORDERS environment gate) and the transport itself,
    which refuses non-GET calls to order endpoints unless the wrapper passed
    allow_live_order=True. There is no sandbox upstream."""


class CredentialsMissing(Exception):
    """Raised when TOSSINVEST_CLIENT_ID / TOSSINVEST_CLIENT_SECRET are absent.

    Fail closed: nothing in this package guesses or defaults credentials.
    """
