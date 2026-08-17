"""Configuration loading.

The API contract lives in config/api.json at the repository root so that base
URL, rate-limit table, and retry policy are reviewable data, not code.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from toss_pilot.errors import CredentialsMissing

REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = REPO_ROOT
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "api.json"

ENV_CLIENT_ID = "TOSSINVEST_CLIENT_ID"
ENV_CLIENT_SECRET = "TOSSINVEST_CLIENT_SECRET"
ENV_CONFIG_PATH = "TOSS_PILOT_CONFIG"

# The live-order opt-in is read from the PROCESS environment only; it is
# deliberately excluded from the .env allowlist below so a forgotten line in a
# file can never silently arm the gate for future runs.
ENV_ALLOW_LIVE = "TOSS_PILOT_ALLOW_LIVE_ORDERS"

_ENV_FILE_ALLOWLIST = (ENV_CLIENT_ID, ENV_CLIENT_SECRET)


def load_config(path: str | Path | None = None) -> dict:
    """Load API configuration JSON. Resolution order: explicit argument,
    TOSS_PILOT_CONFIG environment variable, repository default."""
    if path is None:
        path = os.environ.get(ENV_CONFIG_PATH) or DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_env_file(path: str | Path = REPO_ROOT / ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines, no quoting rules, no expansion.
    Only credential keys are imported (allowlist); in particular the live-order
    flag is never read from a file. Existing environment variables are never
    overwritten. Missing file is not an error; .env is optional and gitignored."""
    env_path = Path(path)
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key in _ENV_FILE_ALLOWLIST and key not in os.environ:
            os.environ[key] = value


def get_credentials() -> tuple[str, str]:
    """Return (client_id, client_secret) from the environment, failing closed
    with a pointer to the WTS issuance page when absent."""
    client_id = os.environ.get(ENV_CLIENT_ID, "").strip()
    client_secret = os.environ.get(ENV_CLIENT_SECRET, "").strip()
    if not client_id or not client_secret:
        raise CredentialsMissing(
            f"Set {ENV_CLIENT_ID} and {ENV_CLIENT_SECRET} in the environment "
            "or in a gitignored .env file. Credentials are issued in Toss "
            "Securities WTS under Settings > Open API."
        )
    return client_id, client_secret
