"""OAuth2 client-credentials token management.

The API allows exactly ONE valid access token per client: re-issuing
immediately invalidates the previous token (spec, POST /oauth2/token). The
manager therefore caches the token on disk and reuses it until near expiry;
issuing is the exception, not the rule. Anything that runs multiple processes
against the same client_id must share this cache file.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from toss_pilot.errors import TossApiError


class TokenManager:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        cache_path: str | Path,
        expiry_margin_seconds: int = 120,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._cache_path = Path(cache_path)
        self._margin = expiry_margin_seconds
        self._timeout = timeout_seconds
        self._transport = transport
        self._token: str | None = None
        self._expires_at: float = 0.0

    def __repr__(self) -> str:  # never leak the secret via logging/repr
        return f"TokenManager(client_id={self._client_id[:6]}..., cache={self._cache_path})"

    def get_token(self, force: bool = False) -> str:
        if not force:
            if self._is_valid():
                return self._token  # type: ignore[return-value]
            self._load_cache()
            if self._is_valid():
                return self._token  # type: ignore[return-value]
        self._issue()
        return self._token  # type: ignore[return-value]

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0

    def _is_valid(self) -> bool:
        return self._token is not None and time.time() < self._expires_at - self._margin

    def _load_cache(self) -> None:
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            self._token = data["access_token"]
            self._expires_at = float(data["expires_at"])
        except (OSError, ValueError, KeyError):
            self._token = None
            self._expires_at = 0.0

    def _save_cache(self) -> None:
        payload = {"access_token": self._token, "expires_at": self._expires_at}
        self._cache_path.write_text(json.dumps(payload), encoding="utf-8")

    def _issue(self) -> None:
        with httpx.Client(transport=self._transport, timeout=self._timeout) as http:
            response = http.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        if response.status_code != 200:
            try:
                body = response.json()
            except ValueError:
                body = {}
            raise TossApiError(
                status_code=response.status_code,
                code=body.get("error", "token-error"),
                message=body.get("error_description", response.text[:200]),
            )
        data = response.json()
        self._token = data["access_token"]
        # expires_in is authoritative per response; 86400 in docs is an example.
        self._expires_at = time.time() + float(data.get("expires_in", 0))
        self._save_cache()
