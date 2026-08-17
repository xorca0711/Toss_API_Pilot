"""Base HTTP client for the Toss Securities Open API.

Handles Bearer auth, the {"result": ...} success envelope, the
{"error": {...}} error envelope, 429 retry honoring Retry-After, and a
single token re-issue on 401 expired-token/invalid-token. Monetary and
quantity values are decimal strings in this API and are returned verbatim;
convert with decimal.Decimal at the call site, never float.
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Any

import httpx

from toss_pilot import config as config_mod
from toss_pilot.auth import TokenManager
from toss_pilot.errors import LiveOrderBlocked, TossApiError

ACCOUNT_HEADER = "X-Tossinvest-Account"
_RETRYABLE_401_CODES = {"expired-token", "invalid-token"}

# Deny-by-default at the transport: any non-GET under these prefixes is a real
# order mutation upstream (no sandbox exists), so it is refused unless the
# caller passes allow_live_order=True AND the process environment opts in.
# The orders.py wrappers set the flag only after their own dry-run gate.
LIVE_ORDER_PREFIXES = ("/api/v1/orders", "/api/v1/conditional-orders")


class TossInvestClient:
    def __init__(
        self,
        config: dict | None = None,
        token_manager: TokenManager | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config or config_mod.load_config()
        if token_manager is None:
            config_mod.load_env_file()
            client_id, client_secret = config_mod.get_credentials()
            # Anchor a relative cache path to the repo root, never the CWD:
            # a CWD-relative cache would drop a live bearer token into
            # whatever directory the CLI happens to run from, outside this
            # repo's .gitignore, and scatter caches that invalidate each
            # other under the one-token-per-client rule.
            cache_path = Path(self._config.get("token_cache_file", ".token_cache.json"))
            if not cache_path.is_absolute():
                cache_path = config_mod.REPO_ROOT / cache_path
            token_manager = TokenManager(
                client_id=client_id,
                client_secret=client_secret,
                token_url=self._config["base_url"] + self._config["token_path"],
                cache_path=cache_path,
                expiry_margin_seconds=self._config.get("token_expiry_margin_seconds", 120),
                timeout_seconds=self._config.get("request_timeout_seconds", 10),
            )
        self._tokens = token_manager
        self._http = httpx.Client(
            base_url=self._config["base_url"],
            timeout=self._config.get("request_timeout_seconds", 10),
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "TossInvestClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        account_seq: int | None = None,
        *,
        allow_live_order: bool = False,
    ) -> Any:
        if method.upper() != "GET" and path.startswith(LIVE_ORDER_PREFIXES):
            if not (
                allow_live_order
                and os.environ.get(config_mod.ENV_ALLOW_LIVE) == "yes"
            ):
                raise LiveOrderBlocked(
                    f"Refusing {method} {path}: order mutations require the "
                    "orders.py wrappers (allow_live_order=True) and "
                    f"{config_mod.ENV_ALLOW_LIVE}=yes in the process "
                    "environment. There is no sandbox upstream."
                )
        max_429_retries = self._config.get("max_retries_429", 3)
        attempts_429 = 0
        retried_auth = False
        while True:
            headers = {"Authorization": f"Bearer {self._tokens.get_token()}"}
            if account_seq is not None:
                headers[ACCOUNT_HEADER] = str(account_seq)
            response = self._http.request(
                method, path, params=params, json=json_body, headers=headers
            )

            if response.status_code == 429 and attempts_429 < max_429_retries:
                attempts_429 += 1
                retry_after = _retry_after_seconds(response)
                time.sleep(retry_after)
                continue

            if response.status_code == 401 and not retried_auth:
                error = _parse_error(response)
                if error.get("code") in _RETRYABLE_401_CODES:
                    retried_auth = True
                    self._tokens.invalidate()
                    self._tokens.get_token(force=True)
                    continue

            if response.status_code >= 400:
                error = _parse_error(response)
                raise TossApiError(
                    status_code=response.status_code,
                    code=error.get("code", "unknown-error"),
                    message=error.get("message", ""),
                    request_id=error.get("requestId"),
                    data=error.get("data"),
                )

            payload = response.json()
            if isinstance(payload, dict) and "result" in payload:
                return payload["result"]
            return payload


def _retry_after_seconds(response: httpx.Response) -> float:
    """Server-controlled header: clamp to a sane bound so a hostile or broken
    value ("inf", "86400") cannot hang the client for hours."""
    try:
        value = float(response.headers.get("Retry-After", "1"))
    except ValueError:
        return 1.0
    if not math.isfinite(value):
        return 1.0
    return min(max(0.0, value), 30.0)


def _parse_error(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"code": "non-json-error", "message": response.text[:200]}
    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            return payload["error"]
        if isinstance(payload.get("error"), str):  # OAuth2-standard shape
            return {
                "code": payload["error"],
                "message": payload.get("error_description", ""),
            }
    return {"code": "unknown-error", "message": str(payload)[:200]}
