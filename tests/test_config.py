"""The .env loader must import only the credential allowlist, so the live
order flag can never be armed invisibly from a file."""

from __future__ import annotations

from toss_pilot import config


def test_env_file_imports_only_allowlisted_keys(tmp_path, monkeypatch):
    monkeypatch.delenv(config.ENV_CLIENT_ID, raising=False)
    monkeypatch.delenv(config.ENV_CLIENT_SECRET, raising=False)
    monkeypatch.delenv(config.ENV_ALLOW_LIVE, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TOSSINVEST_CLIENT_ID=c_abc\n"
        "TOSSINVEST_CLIENT_SECRET=s_def\n"
        "TOSS_PILOT_ALLOW_LIVE_ORDERS=yes\n"
        "SOMETHING_ELSE=1\n",
        encoding="utf-8",
    )

    import os

    config.load_env_file(env_file)
    assert os.environ[config.ENV_CLIENT_ID] == "c_abc"
    assert os.environ[config.ENV_CLIENT_SECRET] == "s_def"
    assert config.ENV_ALLOW_LIVE not in os.environ
    assert "SOMETHING_ELSE" not in os.environ


def test_env_file_never_overwrites_process_env(tmp_path, monkeypatch):
    monkeypatch.setenv(config.ENV_CLIENT_ID, "c_from_process")
    env_file = tmp_path / ".env"
    env_file.write_text("TOSSINVEST_CLIENT_ID=c_from_file\n", encoding="utf-8")

    import os

    config.load_env_file(env_file)
    assert os.environ[config.ENV_CLIENT_ID] == "c_from_process"
